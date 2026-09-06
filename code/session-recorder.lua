local Base = require('code/recorder')
local store = require('code/sessions')
local native = require('code/native')
local validation = require('code/validation')
local Session = setmetatable({}, {__index=Base})

function Session:new(engine,config)
  local o=Base:new({name='unused',rngLogMethod='checkpoints'})
  o.engine=engine
  o.halt=core.allocate(4,true)
  o.status='idle'
  o.autoRecord=not config or config.autoRecord~=false
  return setmetatable(o,{__index=self})
end

-- Called only after the native lobby accepted Start, before its RNG seed call.
function Session:beginMatch()
  if self.engine.loading or not self.engine:singlePlayer() or self.mode=='play' then return end
  if self.mode=='record' and self.status~='armed' then self:reset() end
  if self.autoRecord and self.mode=='none' then self:startRecording() end
end

function Session:saveCopy(name)
  assert(self.engine:singlePlayer() and self.mode=='record' and self.status=='recording'
    and self.active and self.observedTick,'No active recording to save yet')
  for _,key in ipairs({'commandsFile','rngFile','infoFile'}) do assert(self[key]:flush()) end
  assert(self.finalRngData,'Missing ending RNG state')
  return store.copy(self.manifest,name,sha.sha256(self.finalRngData))
end

function Session:guard(callback)
  local ok, reason=xpcall(callback,debug.traceback)
  if not ok then
    if self.status=='error' and (self.active or self.mode~='none') then return false end -- retain the first session failure
    self.status='error'; self.error=tostring(reason)
    local recordingFailed=self.mode=='record'
    local pauseGame=self.engine:singlePlayer() and (self.active or self.mode=='play')
    local stopSimulation=pauseGame and not recordingFailed
    core.writeInteger(self.halt,stopSimulation and 1 or 0)
    if pauseGame then self.engine:pause() end
    if recordingFailed then
      -- A capture failure invalidates the recording, not the player's match.
      -- Keep the first error visible, but detach capture before native dispatch
      -- continues. Ordinary unpause must restore normal commands and ticking.
      self.active=false; self.capturePending=nil
      self.engine:setScope(false)
      self.engine:resetCommands()
    end
    if self.mode=='play' then pcall(self.engine.abortPlayback,self.engine) end
    print('Replay stopped: ' .. self.error)
    if self.manifest then
      pcall(store.write,store.path(self.manifest.id)..'/last-error.txt',self.error)
      if self.mode=='record' then
        self.manifest.status='failed'; pcall(store.save,self.manifest)
      elseif self.mode=='play' then
        pcall(self.playbackResult,self,'failed',{error=self.error})
      end
    end
    for _,key in ipairs({'commandsFile','rngFile','infoFile'}) do
      local file=self[key]; self[key]=nil
      if file then pcall(file.close,file) end
    end
  end
  return ok
end

function Session:playbackResult(status,details)
  local result=details or {}
  result.status=status
  result.started=self.playbackStarted
  result.lastTick=self.engine:tick()
  result.commands=self.playedCommands or 0
  store.write(store.path(self.manifest.id)..'/last-playback.json',json:encode(result))
end

function Session:startRecording()
  assert(self.mode=='none','A replay session is already active')
  assert(self.engine:singlePlayer(),'Recording currently supports single-player Skirmish')
  local automarket=require('code/automarket-replay').current()
  self.manifest=store.new(native.profile)
  self.manifest.automarket=automarket
  self:setName(store.path(self.manifest.id)..'/stream')
  self:openFiles('w')
  self.mode='record'; self.status='armed'; self.active=false
  self.error=nil; self.observedTick=false
  self.finalRngData=nil
  self.executedTick=nil; self.executedBatchSize=0
  self.engine:resetCommands()
  self.engine:setScope(true)
  core.writeInteger(self.halt,0)
end

function Session:activateRecording()
  self:reconcileMode()
  if self.mode~='record' or self.status~='armed' then return end
  local path=store.path(self.manifest.id)
  self.engine:saveSnapshot(path..'/start.sav')
  store.write(path..'/rng.bin',self.engine:rngData())
  self.manifest.snapshotHash=sha.sha256(store.read(path..'/start.sav'))
  self.manifest.rngHash=sha.sha256(store.read(path..'/rng.bin'))
  self.manifest.player=self.engine:player()
  self.manifest.startTick=self.engine:tick()
  self.manifest.lastTick=self.manifest.startTick
  self.manifest.startResources=self.engine:resourceState()
  self.manifest.finalResources=self.manifest.startResources
  local r=self.engine:rngState()
  local seed=core.readInteger(self.engine.rng+4)
  self:saveInfo(0,seed,seed,r[1],r[2],r[4],r[3])
  self.manifest.status='recording'; store.save(self.manifest)
  self.active=true; self.status='recording'
  print('Recording '..self.manifest.id)
end

function Session:prepareRecording()
  -- The start-menu callback returns before the first simulation boundary.
  -- Capture after that initialization, at the same boundary playback verifies.
  if self.mode=='record' and self.status=='armed' then self.capturePending=true end
end

function Session:startPlayback(id)
  assert(self.mode=='none','A replay session is already active')
  assert(self.engine:singlePlayer(),'Replay playback is single-player only')
  if not id then
    for _, item in ipairs(store.list()) do
      if item.status=='complete' and item.variant==native.profile.name then id=item.id; break end
    end
  end
  assert(id,'No completed recording is available')
  local manifest=store.load(id,native.profile)
  assert(store.compatible(manifest),'Replay requires its recorded UCP settings')
  store.preflight(manifest)
  local path=store.path(id)
  local snapshot=store.read(path..'/start.sav')
  local rng=store.read(path..'/rng.bin')
  assert(sha.sha256(snapshot)==manifest.snapshotHash,'Starting save is damaged')
  assert(#rng==0x9c50 and sha.sha256(rng)==manifest.rngHash,'Starting RNG state is damaged')
  self:setName(path..'/stream')
  self:openFiles('r')
  self.manifest=manifest
  self.mode='play'; self.status='loading'; self.active=false
  self.error=nil
  self.playedCommands=0
  self.playbackStarted=os.date('!%Y-%m-%dT%H:%M:%SZ')
  -- Invalidate an earlier success before touching native state. An interrupted
  -- or failed repeat must never retain the previous run's finished report.
  self:playbackResult('loading')
  self.engine:setScope(true)
  core.writeInteger(self.halt,0)
  self.engine:loadSnapshot(path..'/start.sav')
  local bytes={}; for i=1,#rng do bytes[i]=rng:byte(i) end
  core.writeBytes(self.engine.rng,bytes)
  self:checkRngData(manifest.rngHash,'starting save')
  assert(self.engine:tick()==manifest.startTick,'Loaded save has a different starting tick')
  assert(self.engine:player()==manifest.player,'Loaded save has a different player slot')
  self:checkResources(manifest.startResources,'starting save')
  self.active=true; self.status='playing'; self.playedCommands=0
  self.nextCheckpoint=nil
  self:playbackResult('playing')
  print('Playing '..id)
end

function Session:onExecutedCommand(command)
  if self.status~='recording' or not self.active then return end
  validation.sessionCommand(command,self.manifest)
  self.executedBatchSize=command.time==self.executedTick and self.executedBatchSize+1 or 1
  self.executedTick=command.time
  assert(self.executedBatchSize<=100,'Recording exceeds the supported 100-command dispatch batch')
  assert(self.commandsFile:write(json:encode(command)..'\n'))
  assert(self.commandsFile:flush())
  self.manifest.commandCount=self.manifest.commandCount+1
end

function Session:feed()
  self:reconcileMode()
  if self.status~='playing' then return end
  local now=self.engine:tick()
  local count=0
  while true do
    local c=self:peekCommand()
    if not c or c.time>now then return end
    assert(c.time>=now,'Replay command missed its simulation tick')
    count=count+1
    assert(count<=100,'Replay exceeds the native 100-command dispatch batch')
    assert(self.engine:canSchedule(),'Native command ring has no room for the due replay batch')
    validation.sessionCommand(c,self.manifest)
    self.engine:scheduleCommand(c)
    self:consumeSavedCommand()
    self.playedCommands=self.playedCommands+1
  end
end

function Session:onTick()
  self:reconcileMode()
  if self.capturePending then
    self.capturePending=nil
    self:activateRecording()
  end
  if not self.active then return end
  local now=self.engine:tick()
  if self.status=='recording' then
    self.manifest.lastTick=now
    self.manifest.finalRng=self.engine:rngState()
    self.manifest.finalResources=self.engine:resourceState()
    -- Keep the exact last observed boundary; quitting may already change native state.
    -- Hash only checkpoints and completion, not every simulation tick.
    self.finalRngData=self.engine:rngData()
    self.observedTick=true
    if now%64==0 then
      local line=json:encode({time=now,rng=self.engine:rngState(),resources=self.manifest.finalResources,
        rngHash=sha.sha256(self.finalRngData)})
      assert(self.rngFile:write(line..'\n')); assert(self.rngFile:flush())
    end
  elseif self.status=='playing' then
    assert(now<=self.manifest.lastTick,'Replay passed its ending tick')
    if now%64==0 then
      local line=self.rngFile:read()
      assert(line,'Replay verification data ended early')
      local expected=json:decode(line)
      local actual=self.engine:rngState()
      assert(expected.time==now,'Replay checkpoint tick differs')
      for i=1,4 do
        if actual[i]~=expected.rng[i] then
          self.firstDesync={time=now,expected=expected.rng,actual=actual}
          store.write(store.path(self.manifest.id)..'/desync.json',json:encode(self.firstDesync))
          error('RNG divergence at tick '..now..' (field '..i..')')
        end
      end
      self:checkResources(expected.resources,'checkpoint')
      self:checkRngData(expected.rngHash,'checkpoint')
    end
    if now>=self.manifest.lastTick then
      assert(self.playedCommands==self.manifest.commandCount,'Replay ended before all commands were scheduled')
      assert(not self.engine:commandsPending(),'Replay ended with commands still waiting to execute')
      assert(self.engine.journal.executed==self.manifest.commandCount,'Replay native execution count differs')
      local actual=self.engine:rngState()
      for i=1,4 do assert(actual[i]==self.manifest.finalRng[i],'Final RNG state differs at tick '..now) end
      self:checkResources(self.manifest.finalResources,'ending state')
      self:checkRngData(self.manifest.finalRngHash,'ending state')
      self.status='finished'; core.writeInteger(self.halt,1); self.engine:pause()
      self:playbackResult('finished',{rngCheckpoints='matched',
        fullRngCheckpoints='matched',resourceCheckpoints='matched'})
    end
  end
end

function Session:checkRngData(expected,phase)
  validation.hash(expected,'full RNG hash')
  local actual=sha.sha256(self.engine:rngData())
  if actual~=expected then
    self.firstDesync={kind='rng-state',time=self.engine:tick(),phase=phase,expected=expected,actual=actual}
    store.write(store.path(self.manifest.id)..'/desync.json',json:encode(self.firstDesync))
    error('Full RNG state divergence at tick '..self.engine:tick()..' ('..phase..')')
  end
end

function Session:checkResources(expected,phase)
  validation.resources(expected)
  local actual=self.engine:resourceState()
  for i=1,200 do
    if actual[i]~=expected[i] then
      local player=math.floor((i-1)/25)+1
      local resource=(i-1)%25
      self.firstDesync={kind='resources',time=self.engine:tick(),phase=phase,
        player=player,resource=resource,expected=expected[i],actual=actual[i]}
      store.write(store.path(self.manifest.id)..'/desync.json',json:encode(self.firstDesync))
      error('Resource divergence at tick '..self.engine:tick()..' (player '..player..', resource '..resource..')')
    end
  end
end

function Session:reset()
  self.capturePending=nil
  local reportOk,reportError=true,nil
  if self.mode=='play' and (self.status=='playing' or self.status=='loading') and self.manifest then
    reportOk,reportError=pcall(self.playbackResult,self,'interrupted')
  end
  if self.mode=='play' then self.engine:abortPlayback() end
  self.engine:setScope(false)
  self.engine:resetCommands()
  core.writeInteger(self.halt,0)
  local manifest=self.mode=='record' and self.manifest
  local complete=manifest and self.active and self.observedTick and self.status=='recording'
  self.active=false
  local closed,reason=pcall(Base.reset,self)
  if manifest then
    if complete and closed then
      local ok,finishError=pcall(function()
        assert(self.finalRngData,'Missing ending RNG state')
        manifest.finalRngHash=sha.sha256(self.finalRngData)
        store.finish(manifest)
      end)
      if not ok then
        manifest.status='failed'; pcall(store.save,manifest)
        error(finishError)
      end
    else
      manifest.status=(self.status=='error' or not closed) and 'failed' or 'cancelled'
      store.save(manifest)
    end
  end
  assert(closed,reason)
  self.status='idle'; self.manifest=nil; self.nextCheckpoint=nil
  self.observedTick=false; self.error=nil
  self.finalRngData=nil
  core.writeInteger(self.halt,0)
  assert(reportOk,reportError)
end

function Session:reconcileMode()
  if self.mode~='none' and not self.engine:singlePlayer() then
    self.status='error'
    self.error='Replay session ended when entering multiplayer'
    self:reset()
  end
end

function Session:discardFiles() end -- Cancelling never deletes a previous recording.
return Session
