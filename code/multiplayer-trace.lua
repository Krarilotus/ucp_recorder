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
  local environmentHash=store.settings().environmentHash
  validation.hash(environmentHash,'diagnostic environment hash')
  self.network=self.engine:networkState()
  self:write({kind='header',format=5,variant=native.profile.name,executable=native.profile.sha256,
    environmentHash=environmentHash,
    network=self.network,
    localPlayer=self.engine:player(),firstTick=self.engine:tick()})
  if self.network.syncStatus~=0 then self:gap('capture began during native synchronization') end
  print('Multiplayer diagnostics: '..self.path)
end

function M:gap(reason,details)
  self.incomplete=true
  self:record({kind='gap',time=self.engine:tick(),reason=reason,details=details})
end

function M:checkNetwork()
  local state=self.engine:networkState()
  local old=self.network
  local changed=state.mode~=old.mode or state.localPlayer~=old.localPlayer
  for slot=1,8 do
    local a,b=state.roster[slot],old.roster[slot]
    changed=changed or state.handles[slot]~=old.handles[slot] or a.ai~=b.ai or a.variation~=b.variation
  end
  if changed then self:gap('player roster or identity changed',state) end
  if state.syncStatus~=old.syncStatus then self:gap('native synchronization phase changed',state) end
  self.network=state
end

function M:immediateCommand(source)
  -- Lobby commands before the first observed simulation boundary are outside
  -- this diagnostic window. Once open, do not silently omit immediate dispatch.
  if not self.file then return end
  self:checkNetwork()
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'immediate ring slot')
  local address=self.engine.base+0x3c67c+slot*1272
  self:gap('immediate command is outside timed replay coverage',{
    source=source,category=core.readByte(address+8),scheduledTime=core.readInteger(address),
    player=core.readInteger(self.engine.base+self.engine.sites.actorOffset),
    size=core.readInteger(self.engine.base+0x2d830)})
end

function M:systemMessage(source)
  -- Native Receive succeeded and its sender is DPID_SYSMSG (zero). Observe
  -- before the type switch mutates host/roster/timing state. Never read native
  -- pointer fields from a DPMSG or pretend that this header is its full payload.
  if not self.file then return end
  local size=validation.integer(core.readInteger(self.engine.base+0x2d81c),4,61000,'system-message size')
  local address=self.engine.base+0xcd8
  local messageType=core.readInteger(address)
  local details={source=source,messageType=messageType,declaredSize=size}
  if messageType==5 and size>=12 then details.removedHandle=core.readInteger(address+8) end
  self:gap('DirectPlay system message is outside replay coverage',details)
end

function M:record(event)
  self.events=self.events+1
  event.sequence=self.events
  self:write(event)
end

function M:onTick()
  local now=self.engine:tick()
  if self.file then self:checkNetwork() end
  if now%64~=0 or now==self.lastTick then return end
  self:open()
  self.lastTick=now
  self:record({kind='checkpoint',time=now,rng=self.engine:rngState(),resources=self.engine:resourceState(),
    rngHash=sha.sha256(self.engine:rngData())})
end

function M:receivedCommand(address,size,origin)
  validation.integer(size,0,1260,'multiplayer trace payload length')
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'trace ring slot')
  self.received[slot]={size=size,data=utils.tableToHex(core.readBytes(address,size)),origin=origin or 'received'}
end

function M:locallyQueuedCommand()
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'local ring slot')
  local size=core.readInteger(self.engine.base+0x2d830)
  self:receivedCommand(self.engine.base+0x3c67c+slot*1272+10,size,'local')
end

function M:beforeCommand()
  assert(not self.executing,'Nested multiplayer command dispatch')
  local slot=validation.integer(core.readInteger(self.engine.base+0x2d824),0,199,'trace ring slot')
  local address=self.engine.base+0x3c67c+slot*1272
  self:open()
  self:checkNetwork()
  local source=self.received[slot]
  local event={kind=source and 'command' or 'untracked',time=self.engine:tick(),slot=slot,
    scheduledTime=core.readInteger(address),handle=core.readInteger(address+4),
    player=core.readInteger(self.engine.base+self.engine.sites.actorOffset),category=core.readByte(address+8)}
  if source then
    event.origin=source.origin
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
  self.network=nil
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
