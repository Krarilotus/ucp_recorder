local Base = require('code/recorder')
local store = require('code/sessions')
local native = require('code/native')
local validation = require('code/validation')
local Session = setmetatable({}, {__index=Base})

function Session:new(engine)
  local o=Base:new({name='unused',rngLogMethod='checkpoints'})
  o.engine=engine
  o.halt=core.allocate(4,true)
  o.status='idle'
  return setmetatable(o,{__index=self})
end

function Session:guard(callback)
  local ok, reason=xpcall(callback,debug.traceback)
  if not ok then
    if self.status=='error' and (self.active or self.mode~='none') then return false end -- retain the first session failure
    self.status='error'; self.error=tostring(reason)
    local stopSimulation=self.active or self.mode=='play'
    core.writeInteger(self.halt,stopSimulation and 1 or 0)
    if stopSimulation then self.engine:pause() end
    print('Replay stopped: ' .. self.error)
    if self.manifest then
      pcall(store.write,store.path(self.manifest.id)..'/last-error.txt',self.error)
      if self.mode=='record' then
        self.manifest.status='failed'; pcall(store.save,self.manifest)
      end
    end
    for _,key in ipairs({'commandsFile','rngFile','infoFile'}) do
      local file=self[key]; self[key]=nil
      if file then pcall(file.close,file) end
    end
  end
  return ok
end

function Session:startRecording()
  assert(self.mode=='none','A replay session is already active')
  assert(self.engine:singlePlayer(),'Recording currently supports single-player Skirmish')
  self.manifest=store.new(native.profile)
  self:setName(store.path(self.manifest.id)..'/stream')
  self:openFiles('w')
  self.mode='record'; self.status='armed'; self.active=false
  self.error=nil; self.observedTick=false
  core.writeInteger(self.halt,0)
end

function Session:activateRecording()
  if self.mode~='record' or self.status~='armed' then return end
  local path=store.path(self.manifest.id)
  self.engine:saveSnapshot(path..'/start.sav')
  store.write(path..'/rng.bin',core.readString(self.engine.rng,0x9c50))
  self.manifest.snapshotHash=sha.sha256(store.read(path..'/start.sav'))
  self.manifest.rngHash=sha.sha256(store.read(path..'/rng.bin'))
  self.manifest.player=self.engine:player()
  self.manifest.startTick=self.engine:tick()
  self.manifest.lastTick=self.manifest.startTick
  local r=self.engine:rngState()
  local seed=core.readInteger(self.engine.rng+4)
  self:saveInfo(0,seed,seed,r[1],r[2],r[4],r[3])
  self.manifest.status='recording'; store.save(self.manifest)
  self.active=true; self.status='recording'
  print('Recording '..self.manifest.id)
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
  core.writeInteger(self.halt,0)
  self.engine:loadSnapshot(path..'/start.sav')
  local bytes={}; for i=1,#rng do bytes[i]=rng:byte(i) end
  core.writeBytes(self.engine.rng,bytes)
  assert(self.engine:tick()==manifest.startTick,'Loaded save has a different starting tick')
  assert(self.engine:player()==manifest.player,'Loaded save has a different player slot')
  self.active=true; self.status='playing'; self.playedCommands=0
  self.nextCheckpoint=nil
  print('Playing '..id)
end

function Session:onCommand(category,time,address,size)
  if self.status~='recording' or not self.active or time<=0 then return end
  validation.integer(size,0,1260,'native command size')
  validation.sessionCommand({commandCategory=category,time=time,player=self.engine:player(),
    size=size,data=require('code/utils').tableToHex(core.readBytes(address,size))},self.manifest)
  self:saveCommand(category,time,address,size,self.engine:player())
  self.manifest.commandCount=self.manifest.commandCount+1
end

function Session:feed()
  if self.status~='playing' then return end
  local now=self.engine:tick()
  while self.engine:canSchedule() do
    local c=self:peekCommand()
    if not c or c.time>now+64 then return end
    assert(c.time>=now,'Replay command missed its simulation tick')
    validation.sessionCommand(c,self.manifest)
    self.engine:scheduleCommand(c)
    self:consumeSavedCommand()
    self.playedCommands=self.playedCommands+1
  end
end

function Session:onTick()
  if not self.active then return end
  local now=self.engine:tick()
  if self.status=='recording' then
    self.manifest.lastTick=now
    self.manifest.finalRng=self.engine:rngState()
    self.observedTick=true
    if now%64==0 then
      local line=json:encode({time=now,rng=self.engine:rngState()})
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
    end
    if now>=self.manifest.lastTick then
      assert(self.playedCommands==self.manifest.commandCount,'Replay ended before all commands were scheduled')
      assert(not self.engine:commandsPending(),'Replay ended with commands still waiting to execute')
      local actual=self.engine:rngState()
      for i=1,4 do assert(actual[i]==self.manifest.finalRng[i],'Final RNG state differs at tick '..now) end
      self.status='finished'; core.writeInteger(self.halt,1); self.engine:pause()
      store.write(store.path(self.manifest.id)..'/last-playback.json',json:encode({
        status='finished',lastTick=now,commands=self.playedCommands,rngCheckpoints='matched'}))
    end
  end
end

function Session:reset()
  local manifest=self.mode=='record' and self.manifest
  local complete=manifest and self.active and self.observedTick and self.status=='recording'
  self.active=false
  local closed,reason=pcall(Base.reset,self)
  if manifest then
    if complete and closed then
      local ok,finishError=pcall(store.finish,manifest)
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
  core.writeInteger(self.halt,0)
end

function Session:discardFiles() end -- Cancelling never deletes a previous recording.
return Session
