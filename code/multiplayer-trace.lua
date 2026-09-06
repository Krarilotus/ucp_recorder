-- Opt-in observation only: never pause, patch state, inject or suppress commands.
local store=require('code/sessions')
local platform=require('code/platform')
local native=require('code/native')
local validation=require('code/validation')
local utils=require('code/utils')
local tr=require('code/locale').text
local unpack=table.unpack or unpack
local M={ROOT='ucp/replay-diagnostics'}

function M.new(engine,config)
  config=config or {}
  local last=validation.integer(config.multiplayerDiagnosticsEndTick or 0,0,2147483584,'diagnostic end tick')
  local window
  if last>0 then
    local first=validation.integer(config.multiplayerDiagnosticsStartTick or 64,64,last-64,'diagnostic start tick')
    assert(first%64==0 and last%64==0,'Diagnostic window ticks must be multiples of 64')
    window={startTick=first,endTick=last}
  end
  return setmetatable({engine=engine,received={},count=0,window=window,rngCalls={}},{__index=M})
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
  self.count=0; self.events=0; self.gaps=0; self.rngCalls={}; self.lastResult=nil
  self.pendingNativeHashes={}
  local environmentHash=store.settings().environmentHash
  validation.hash(environmentHash,'diagnostic environment hash')
  self.network=self.engine:networkState()
  self:write({kind='header',format=self.window and 6 or 5,window=self.window,
    variant=native.profile.name,executable=native.profile.sha256,
    environmentHash=environmentHash,
    network=self.network,rngAttribution=true,immediatePayloadSource='native-fixed-v1',
    nativeWorldHashes=self.nativeWorldHashes,
    localPlayer=self.engine:player(),firstTick=self.engine:tick()})
  if self.network.syncStatus~=0 then self:gap('capture began during native synchronization') end
  if self.window and self.engine:tick()~=self.window.startTick then
    self:gap('diagnostic start boundary missed')
  end
  print('Multiplayer diagnostics: '..self.path)
end

function M:gap(reason,details)
  self.incomplete=true
  self.gaps=(self.gaps or 0)+1
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
  -- Immediate serialization/receive-copy targets the 61,000-byte fixed buffer.
  -- The ring holds the command header, but its payload is unused on this path.
  local size=validation.integer(core.readInteger(self.engine.base+0x2d830),0,61000,'immediate payload size')
  self:gap('immediate command is outside timed replay coverage',{
    source=source,category=core.readByte(address+8),scheduledTime=core.readInteger(address),
    player=core.readInteger(self.engine.base+self.engine.sites.actorOffset),
    size=size,handle=core.readInteger(address+4),
    data=utils.tableToHex(core.readBytes(self.engine.base+0x2d834,size))})
end

function M:rngCall(stream,stack)
  if not self.file then return end
  local address=core.readInteger(stack)
  if address<0 then address=address+4294967296 end
  -- Scope gates relocate CALLs into allocated code. Compare their native return
  -- addresses, not allocation addresses that can differ between processes.
  address=(self.rngReturnAddresses or {})[address] or address
  local key=stream..':'..address
  local entry=self.rngCalls[key]
  if not entry then
    -- Bound diagnostic memory even if another extension generates many callers.
    assert(self.rngCallerCount==nil or self.rngCallerCount<512,'Too many RNG diagnostic callers')
    entry={stream=stream,returnAddress=address,count=0}
    self.rngCalls[key]=entry
    self.rngCallerCount=(self.rngCallerCount or 0)+1
  end
  entry.count=entry.count+1
end

function M:rngEvidence()
  local entries={}
  for _,entry in pairs(self.rngCalls) do entries[#entries+1]=entry end
  table.sort(entries,function(a,b)
    return a.stream<b.stream or (a.stream==b.stream and a.returnAddress<b.returnAddress)
  end)
  self.rngCalls={}; self.rngCallerCount=0
  return entries
end

function M:worldHash()
  if not self.file then return end
  self:checkNetwork()
  local player=validation.integer(self.engine:player(),1,8,'native hash player')
  local base=self.engine.base
  local function unsigned(address)
    local value=core.readInteger(address)
    if value<0 then value=value+4294967296 end
    return validation.integer(value,0,4294967295,'native hash value')
  end
  local tick=validation.integer(core.readInteger(base+0x7a8bc+player*4),0,self.engine:tick(),'native hash tick')
  local total=unsigned(base+0x7a898+player*4)
  local domains,sum={},0
  for i=0,13 do
    domains[i+1]=unsigned(base+0x7a8e0+player*48+i*4)
    sum=(sum+domains[i+1])%4294967296
  end
  assert(sum==total,'Native hash subtotals do not match completed total')
  assert(#self.pendingNativeHashes<256,'Too many native hash observations between checkpoints')
  self.pendingNativeHashes[#self.pendingNativeHashes+1]={player=player,time=tick,total=total,domains=domains}
end

function M:worldHashEvidence()
  local entries=self.pendingNativeHashes
  self.pendingNativeHashes={}
  return entries
end

function M:statusLines()
  if self.failed then return {tr('Test capture stopped: %s',tostring(self.failureReason or 'error'):match('^[^\n]+')),
    tr('Multiplayer replay playback is not available.')} end
  if self.file then
    local ending=self.window and tostring(self.window.endTick) or tr('match exit')
    return {tr('Test capture active: tick %d / %s',self.engine:tick(),ending),
      tr('%d commands; %d uncovered network events.',self.count,self.gaps or 0),
      tr('Saved automatically. This is not a playable replay.')}
  end
  if self.lastResult then
    return {tr(self.lastResult.status=='complete' and 'Test capture saved at tick %s.'
        or 'Incomplete test capture saved at tick %s.',tostring(self.lastResult.lastTick or '?')),
      tr('%d commands; %d uncovered network events.',self.lastResult.commands,self.lastResult.gaps),
      tr('Capture ended; further actions are not being saved.'),
      tr('This is not a playable multiplayer replay.')}
  end
  return {self.window and tr('Waiting for multiplayer test capture at tick %d.',self.window.startTick)
      or tr('Waiting for multiplayer test capture.'),
    tr('Multiplayer replay playback is not available.')}
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
    rngHash=sha.sha256(self.engine:rngData()),rngCalls=self:rngEvidence(),worldHashes=self:worldHashEvidence()})
  if self.window and now==self.window.endTick then self:finishWindow() end
end

function M:finishWindow()
  local path=self.path
  self:stop('diagnostic window ended')
  self.closed=true -- Do not reopen because of later commands or peer departure.
  print('Multiplayer diagnostic window saved: '..tostring(path))
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
      local incomplete=self.incomplete or self.executing
        or (self.window and self.lastTick~=self.window.endTick)
      self:write({kind='end',status=incomplete and 'incomplete' or 'complete',lastTick=self.lastTick,
        commands=self.count,events=self.events,reason=reason,pendingNativeHashes=#self.pendingNativeHashes})
      self.lastResult={path=self.path,lastTick=self.lastTick,commands=self.count,gaps=self.gaps or 0,
        status=incomplete and 'incomplete' or 'complete'}
    end)
    self.file=nil
    local closed,closeError=f:close()
    assert(ok and closed,err or closeError)
  end
  self.received={}; self.executing=nil; self.failed=false; self.incomplete=false; self.path=nil
  self.rngCalls={}; self.rngCallerCount=0; self.failureReason=nil
  self.pendingNativeHashes={}
  self.lastTick=nil
  self.network=nil
  self.closed=false
  self.simulationObserved=false
end

function M:observe(event,...)
  if (self.failed or self.closed) and event~='stop' then return end
  local args={...}
  local ok,reason=pcall(function()
    if event~='stop' and self.engine:singlePlayer() then
      if self.simulationObserved or self.file or next(self.received) then self:stop('left multiplayer') end
      return
    end
    -- Loading and lobby code also call the shared RNG and command observers.
    -- Their tick/roster fields may still describe an earlier game. Only the
    -- native simulation boundary establishes that gameplay has begun. Keep
    -- queued payloads, but never open/seal a window from pre-simulation events.
    if event=='onTick' then self.simulationObserved=true end
    local receipt=event=='receivedCommand' or event=='locallyQueuedCommand'
    if event~='stop' and not self.simulationObserved then
      if receipt then self[event](self,unpack(args)) end
      return
    end
    if self.window and event~='stop' then
      local now=self.engine:tick()
      if now>self.window.endTick then
        self:open()
        self:gap('diagnostic end boundary missed')
        self:finishWindow()
        return
      end
      -- Keep receipts from before the window: a queued command may execute
      -- inside it. Only executed events/checkpoints define the capture window.
      if event~='receivedCommand' and event~='locallyQueuedCommand' then
        if now<self.window.startTick then return end
        self:open()
      end
    end
    self[event](self,unpack(args))
  end)
  if not ok then
    self.failed=true; self.executing=nil; self.failureReason=tostring(reason)
    local f=self.file; self.file=nil
    if f then pcall(f.close,f) end
    if self.path then pcall(store.write,self.path..'/error.txt',tostring(reason)) end
    print('Multiplayer diagnostics stopped: '..tostring(reason))
  end
end

return M
