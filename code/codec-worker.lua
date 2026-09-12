-- One native compression thread, private inputs/outputs only. No Lua callback,
-- game-world read, native save, or network call runs on this thread.
local platform=require('code/platform')
local M={STRIDE=28,MAX_BYTES=32*1024*1024}
local api,entry
local Job={}

-- stdcall(job): count, descriptors, decoder state, compressor, cancellation.
-- Row: input, output, raw size, success, packed size, CRC, compression enabled.
-- All addresses are allocated by the caller; the original codec uses private
-- stack/GlobalAlloc workspace. Nonvolatile registers and the thread ABI survive.
function M.code()
  local b={}; local labels,branches={},{}
  local function emit(...) for _,v in ipairs({...}) do b[#b+1]=v end end
  local function branch(op,label) emit(0x0f,op); branches[#branches+1]={#b,label}; emit(0,0,0,0) end
  emit(0x53,0x55,0x56,0x57,0x8b,0x7c,0x24,0x14) -- save; edi=job
  emit(0x8b,0x2f,0x8b,0x77,0x04) -- ebp=count; esi=rows
  labels.again=#b
  emit(0x85,0xed); branch(0x84,'done')
  emit(0x83,0x7f,0x10,0); branch(0x85,'done')
  emit(0x83,0x7e,0x18,0); branch(0x84,'next')
  emit(0x8b,0x4f,0x08) -- ecx=private decoder
  emit(0xff,0x76,0x08,0xff,0x76,0x04,0xff,0x36) -- size, output, input
  emit(0x8d,0x46,0x10,0x50,0x8d,0x46,0x14,0x50) -- size out, CRC out
  emit(0xff,0x57,0x0c,0x89,0x46,0x0c) -- native thiscall; success
  labels.next=#b
  emit(0x83,0xc6,M.STRIDE,0x4d); branch(0x85,'again')
  labels.done=#b
  emit(0x31,0xc0,0x5f,0x5e,0x5d,0x5b,0xc2,0x04,0x00)
  for _,ref in ipairs(branches) do
    local value=(assert(labels[ref[2]])-ref[1]-4)%4294967296
    for i=1,4 do b[ref[1]+i]=value%256; value=math.floor(value/256) end
  end
  return b
end

local function initialize()
  if api then return end
  local functions={}
  for name,count in pairs({CreateThread=6,WaitForSingleObject=2,CloseHandle=1,SetThreadPriority=2}) do
    functions[name]=platform.stdcall('kernel32.dll',name,count)
  end
  local code=M.code(); entry=core.allocateCode(#code); core.writeCode(entry,code)
  api=functions
end

function M.new(inputs,compressor)
  initialize()
  assert(#inputs>0 and #inputs<=150,'Invalid compression batch')
  local total=0
  for _,input in ipairs(inputs) do
    require('code/validation').integer(input.size,1,M.MAX_BYTES,'worker input size')
    total=total+input.size
  end
  assert(total<=M.MAX_BYTES,'Compression batch exceeds memory budget')
  local self=setmetatable({count=#inputs},{__index=Job})
  local ok,reason=pcall(function()
    self.memory=core.allocate(40+#inputs*M.STRIDE+total,true)
    assert(self.memory and self.memory~=0,'Cannot allocate compression output')
    local state,rows=self.memory+20,self.memory+40
    core.writeInteger(self.memory,#inputs); core.writeInteger(self.memory+4,rows)
    core.writeInteger(self.memory+8,state); core.writeInteger(self.memory+12,compressor)
    core.writeInteger(self.memory+16,0)
    core.writeInteger(state,0); core.writeInteger(state+4,4096)
    local output=rows+#inputs*M.STRIDE
    for i,input in ipairs(inputs) do
      local row=rows+(i-1)*M.STRIDE
      core.writeInteger(row,input.address); core.writeInteger(row+4,output)
      core.writeInteger(row+8,input.size); core.writeInteger(row+12,0)
      core.writeInteger(row+16,0); core.writeInteger(row+20,0)
      core.writeInteger(row+24,input.compress and 1 or 0)
      output=output+input.size
    end
    self.thread=api.CreateThread(0,0,entry,self.memory,0,0)
    if not self.thread or self.thread==0 then self.thread=nil; error('Cannot start compression worker') end
    pcall(api.SetThreadPriority,self.thread,-1) -- below normal; gameplay has priority
  end)
  if not ok then if self.memory and not self.thread then core.deallocate(self.memory) end; error(reason) end
  return self
end

function Job:ready()
  if self.completed then return true end
  local state=api.WaitForSingleObject(assert(self.thread),0)
  assert(state==0 or state==258,'Cannot observe compression worker')
  if state==258 then return false end
  assert(api.CloseHandle(self.thread)~=0,'Cannot close compression worker handle')
  self.thread=nil; self.completed=true
  return true
end

function Job:packed(index)
  assert(self.completed and not self.cancelled,'Compression is not available')
  require('code/validation').integer(index,1,self.count,'compression section')
  local row=self.memory+40+(index-1)*M.STRIDE
  if core.readInteger(row+12)~=1 then return end -- original codec fallback: raw section
  local size,raw=core.readInteger(row+16),core.readInteger(row+8)
  assert(size>0 and size<=raw,'Invalid compressed section size')
  if size+12>=raw then return end
  return core.readString(row+8,4)..core.readString(row+16,8)..core.readString(core.readInteger(row+4),size)
end

function Job:cancel()
  self.cancelled=true; core.writeInteger(self.memory+16,1)
end

function Job:close()
  assert(self:ready(),'Cannot release memory still owned by compression worker')
  core.deallocate(self.memory); self.memory=nil
end
return M
