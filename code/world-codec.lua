-- Use the game's PKWARE primitives on private data, never its global decoder or
-- multiplayer save routine. Callers own source stability; the codec never yields.
local binary=require('code/binary-memory')
local build=require('code/build-profile')
local M={MAX_SECTION=32*1024*1024}
-- Shared SHC/Extreme wrappers: private 0x8dd8 workspace, allocation/lock
-- failures, five stack arguments and thiscall cleanup. Relocatable imports and
-- memset calls are wildcarded; no game decoder singleton is used.
local contexts={
  implode='83 EC 34 55 56 57 68 D8 8D 00 00 6A 42 8B F1 BD 01 00 00 00 FF 15 ? ? ? ? 8B F8 85 FF 75 09 5F 5E 5D 83 C4 34 C2 14 00 53 57 FF 15 ? ? ? ? 8B D8 85 DB 75 13 57 FF 15 ? ? ? ? 5B 5F 5E 33 C0 5D 83 C4 34 C2 14 00 6A 34 8D 44 24 14 6A 00 50 E8 ? ? ? ? 8B 44 24 64 8B 4C 24 5C 8B 54 24 60',
  explode='83 EC 34 53 56 68 D8 8D 00 00 6A 42 BB 01 00 00 00 FF 15 ? ? ? ? 8B F0 85 F6 75 08 5E 5B 83 C4 34 C2 14 00 57 56 FF 15 ? ? ? ? 8B F8 85 FF 75 12 56 FF 15 ? ? ? ? 5F 5E 33 C0 5B 83 C4 34 C2 14 00 6A 34 8D 44 24 10 6A 00 50 E8 ? ? ? ? 8B 54 24 58 8B 4C 24 54 8B 44 24 5C',
}
local functions

---@class RecorderWorldCodec
---@field capacity integer
---@field state integer
---@field input integer
---@field output integer
local Codec={}

local function prepare()
  if functions then return functions end
  local sites={}
  for name,pattern in pairs(contexts) do
    sites[name]=require('code/hook-check').resolve(pattern,'Recorder native world codec '..name).address
  end
  binary.prepare()
  functions={implode=core.exposeCode(sites.implode,6,1),explode=core.exposeCode(sites.explode,6,1),address=sites.implode}
  return functions
end

function M.compressorAddress() return prepare().address end

-- nil means store the original section without compression. The native primitive
-- limits its output to the input size and reports allocation/overflow failures;
-- encodeData itself ignores that result, so it must not be used here.
---@param data string
---@return string|nil
function Codec:compress(data)
  assert(self.state,'Native world codec buffers have been released')
  assert(type(data)=='string' and #data>0 and #data<=self.capacity,'Invalid world section size')
  binary.write(self.input,data)
  core.writeInteger(self.state+8,0)
  core.writeInteger(self.state+12,#data)
  core.writeInteger(self.state+16,0)
  if functions.implode(self.state,self.state+8,self.state+16,self.input,self.output,#data)~=1 then return end
  local size=core.readInteger(self.state+16)
  assert(size>0 and size<=#data,'Native world compression returned an invalid size')
  if size+12>=#data then return end
  local checksum=core.readString(self.state+8,4)
  local header=core.readString(self.state+12,8)..checksum
  -- Release uses the original encoder's status, bounds and CRC, just as the
  -- native container does. The diagnostic build additionally decodes/compares
  -- each section; that duplicate work does not belong in live release capture.
  if build.diagnostics then
    assert(functions.explode(self.state,self.state+8,self.output,size,self.input,#data)==1,
      'Native world compression failed to round-trip')
    assert(core.readString(self.state+8,4)==checksum and core.readString(self.input,#data)==data,
      'Native world compression changed section bytes')
  end
  local result=header..core.readString(self.output,size)
  assert(#result==size+12,'Short native compressed section read')
  return result
end

-- A bounded lifetime avoids retaining tens of MiB or leaking buffers on error.
---@param capacity integer
---@param callback fun(codec: RecorderWorldCodec): any
---@return any
function M.withBuffers(capacity,callback)
  require('code/validation').integer(capacity,1,M.MAX_SECTION,'World codec capacity')
  prepare()
  local allocated={}
  local codec=setmetatable({capacity=capacity},{__index=Codec})
  local ok,result=xpcall(function()
    local function allocate(size)
      local pointer=core.allocate(size,true)
      assert(type(pointer)=='number' and pointer~=0,'Cannot allocate native world codec buffer')
      allocated[#allocated+1]=pointer
      return pointer
    end
    codec.state=allocate(20)
    codec.input=allocate(capacity+1) -- allow a trailing NUL from a string-copy bridge
    codec.output=allocate(capacity)
    core.writeInteger(codec.state,0) -- CMP_BINARY
    core.writeInteger(codec.state+4,4096)
    return callback(codec)
  end,debug.traceback)
  codec.state=nil
  local cleanupError
  for i=#allocated,1,-1 do
    local freed,reason=pcall(core.deallocate,allocated[i])
    if not freed then cleanupError=cleanupError or tostring(reason) end
  end
  assert(ok,result)
  assert(not cleanupError,cleanupError)
  return result
end
return M
