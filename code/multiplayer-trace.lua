-- Opt-in observation only: never pause, patch state, inject or suppress commands.
local store=require('code/sessions')
local platform=require('code/platform')
local native=require('code/native')
local validation=require('code/validation')
local utils=require('code/utils')
local unpack=table.unpack or unpack
local M={ROOT='ucp/replay-diagnostics'}

function M.new(engine)
  return setmetatable({engine=engine,received={},count=0},{__index=M})
end

function M:write(value)
  assert(self.file:write(json:encode(value)..'\n'))
  assert(self.file:flush())
end

function M:open()
  if self.file then return end
  platform.mkdir(M.ROOT)
  local prefix=os.date('!%Y%m%d-%H%M%S')
  for i=1,9999 do
    local path=M.ROOT..'/'..prefix..'-'..string.format('%04d',i)
    if platform.mkdir(path) then self.path=path; break end
    assert(i<9999,'Cannot allocate multiplayer trace folder')
  end
  self.file=assert(io.open(self.path..'/commands.jsonl','w'))
  self.count=0; self.events=0
  self:write({kind='header',format=2,variant=native.profile.name,executable=native.profile.sha256,
    localPlayer=self.engine:player(),firstTick=self.engine:tick()})
  print('Multiplayer diagnostics: '..self.path)
end

function M:record(event)
  self.events=self.events+1
  event.sequence=self.events
  self:write(event)
end

function M:onTick()
  local now=self.engine:tick()
  if now%64~=0 or now==self.lastTick then return end
  self:open()
  self.lastTick=now
  self:record({kind='checkpoint',time=now,rng=self.engine:rngState(),resources=self.engine:resourceState()})
end

function M:receivedCommand(address,size)
  validation.integer(size,0,1260,'multiplayer trace payload length')
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'trace ring slot')
  self.received[slot]={size=size,data=utils.tableToHex(core.readBytes(address,size))}
end

function M:beforeCommand()
  assert(not self.executing,'Nested multiplayer command dispatch')
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'trace ring slot')
  local address=self.engine.base+0x3c67c+slot*1272
  self:open()
  local source=self.received[slot]
  local event={kind=source and 'command' or 'untracked',time=self.engine:tick(),slot=slot,
    scheduledTime=core.readInteger(address),handle=core.readInteger(address+4),
    player=core.readInteger(self.engine.base+self.engine.sites.actorOffset),category=core.readByte(address+8)}
  if source then
    event.size=source.size
    event.data=utils.tableToHex(core.readBytes(address+10,source.size))
    event.changedSinceReceive=event.data~=source.data
  else self.incomplete=true end
  self.executing=event
end

function M:afterCommand()
  local event=self.executing
  if not event then return end
  self.executing=nil
  self.received[event.slot]=nil
  self.count=self.count+1
  event.rng=self.engine:rngState()
  event.resources=self.engine:resourceState()
  self:record(event)
end

function M:stop(reason)
  local f=self.file
  if f then
    local ok,err=pcall(function()
      self:write({kind='end',status=(self.incomplete or self.executing) and 'incomplete' or 'complete',
        commands=self.count,events=self.events,reason=reason})
    end)
    self.file=nil
    local closed,closeError=f:close()
    assert(ok and closed,err or closeError)
  end
  self.received={}; self.executing=nil; self.failed=false; self.incomplete=false; self.path=nil
  self.lastTick=nil
end

function M:observe(event,...)
  if self.failed and event~='stop' then return end
  local args={...}
  local ok,reason=pcall(function()
    if event~='stop' and self.engine:singlePlayer() then
      if self.file or next(self.received) then self:stop('left multiplayer') end
      return
    end
    self[event](self,unpack(args))
  end)
  if not ok then
    self.failed=true; self.executing=nil
    local f=self.file; self.file=nil
    if f then pcall(f.close,f) end
    if self.path then pcall(store.write,self.path..'/error.txt',tostring(reason)) end
    print('Multiplayer diagnostics stopped: '..tostring(reason))
  end
end

return M
