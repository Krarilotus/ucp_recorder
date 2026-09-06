-- Optional SP diagnostics. File/limit failures stop this observer, never the match.
local store=require('code/sessions')
local platform=require('code/platform')
local native=require('code/native')
local bit=require('bit')
local M={MAX_BYTES=64*1024*1024,MAX_CALLERS=512}

function M.new(engine)
  return setmetatable({engine=engine},{__index=M})
end

function M:clear()
  self.calls={}; self.callers=0; self.count=0; self.order=0
end

function M:write(value)
  local line=json:encode(value)..'\n'
  assert(self.bytes+#line<=M.MAX_BYTES,'RNG attribution reached its 64 MiB limit')
  assert(self.file:write(line)); assert(self.file:flush())
  self.bytes=self.bytes+#line
end

function M:begin(manifest,mode)
  self:finish('replaced')
  local root=store.path(manifest.id)..'/rng-attribution'
  platform.mkdir(root)
  local prefix=mode..'-'..os.date('!%Y%m%d-%H%M%S')
  for i=1,9999 do
    local path=root..'/'..prefix..'-'..string.format('%04d',i)
    if platform.mkdir(path) then self.path=path; break end
    assert(i<9999,'Cannot allocate RNG attribution folder')
  end
  self.file=assert(io.open(self.path..'/calls.jsonl','w'))
  self.bytes=0; self:clear(); self.failed=nil
  self.previousTick=self.engine:tick()
  self:write({kind='header',format=1,mode=mode,replay=manifest.id,
    variant=native.profile.name,executable=native.profile.sha256,
    firstTick=self.previousTick,rng=self.engine:rngState()})
end

function M:rngCall(stream,stack)
  if not self.file or not self.engine:singlePlayer() then return end
  local address=core.readInteger(stack)%4294967296
  address=(self.returnAddresses or {})[address] or address
  local tick=self.engine:tick()
  local key=stream..':'..address
  local entry=self.calls[key]
  if not entry then
    assert(self.callers<M.MAX_CALLERS,'RNG attribution caller limit reached')
    entry={stream=stream,returnAddress=address,count=0,firstTick=tick,lastTick=tick}
    self.calls[key]=entry; self.callers=self.callers+1
  end
  entry.count=entry.count+1; entry.lastTick=tick
  self.count=self.count+1
  -- A diagnostic ordering checksum, not a proof of equal simulation state.
  self.order=bit.bxor(bit.rol(self.order,5),address,tick,stream)
end

function M:checkpoint()
  if not self.file then return end
  local now=self.engine:tick()
  local entries={}
  for _,entry in pairs(self.calls) do entries[#entries+1]=entry end
  table.sort(entries,function(a,b)
    return a.stream<b.stream or (a.stream==b.stream and a.returnAddress<b.returnAddress)
  end)
  self:write({kind='checkpoint',fromTick=self.previousTick,time=now,
    rng=self.engine:rngState(),count=self.count,order=self.order%4294967296,calls=entries})
  self.previousTick=now; self:clear()
end

function M:finish(reason)
  if not self.file then return end
  if self.count>0 or self.engine:tick()~=self.previousTick then self:checkpoint() end
  self:write({kind='end',time=self.engine:tick(),reason=reason})
  local file=self.file; self.file=nil
  assert(file:close())
end

function M:observe(method,...)
  local ok,reason=pcall(self[method],self,...)
  if not ok then
    self.failed=tostring(reason)
    local file=self.file; self.file=nil
    if file then pcall(file.close,file) end
    self:clear()
    print('RNG attribution stopped: '..self.failed)
  end
end

return M
