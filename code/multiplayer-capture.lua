-- Durable, read-only capture on each peer. This is not offline playback.
local Trace=require('code/multiplayer-trace')
local files=require('code/capture-files')
local store=require('code/sessions')
local tr=require('code/locale').text
local verification=require('code/replay-verification')
local M={ROOT='ucp/replays',MAX_BYTES=256*1024*1024,MAX_TICK_BYTES=128*1024*1024}
setmetatable(M,{__index=Trace})

function M.new(engine,config)
  -- Full-match persistence must never inherit a bounded diagnostic window.
  local self=Trace.new(engine,{})
  self.root=M.ROOT
  self.fileMode='wb' -- byte offsets must not change through Windows CRLF translation
  self.rngAttribution=config and config.multiplayerDiagnostics==true
  self.verificationProfile=verification.recordingProfile()
  return setmetatable(self,{__index=M})
end

function M:write(value)
  local line=json:encode(value)..'\n'
  assert((self.bytes or 0)+#line<=M.MAX_BYTES,'Multiplayer capture reached its 256 MiB limit')
  assert(self.file:write(line)); assert(self.file:flush())
  self.bytes=(self.bytes or 0)+#line
end

function M:open()
  if self.file then return end
  self.bytes=0
  self.lastNamedCopy=nil
  self.clock=nil
  self.pendingTick=nil; self.tickBytes=0
  self.finalRngData=nil; self.finalResourceData=nil
  self.recoveryPending=nil; self.boundaryEvents=nil
  Trace.open(self)
  self.capture=files.begin(self.path,self.engine,store.settings())
  self.capture.verificationProfile=self.verificationProfile
  if self.engine.battle then self.engine.battle:begin() end
  self.tickFile=assert(io.open(self.path..'/ticks.bin','wb'))
  self.capture.tickProfile='native-tick-rng-v1'
  self.capture.traceHeaderBytes=self.bytes
  files.save(self.capture)
end

function M:timeline(now)
  if self.clock and now<self.clock then
    -- Preserve evidence across a restored simulation clock without merging it
    -- into the old timeline or claiming the replacement world was captured.
    self.incomplete=true; self.gaps=(self.gaps or 0)+1
    Trace.record(self,{kind='gap',time=now,reason='simulation clock moved backwards',
      details={previousTick=self.clock}})
    self.lastTick=nil
    self.recoveryPending='simulation clock moved backwards'
  end
  self.clock=now
end

function M:record(event)
  self:timeline(event.time)
  Trace.record(self,event)
end

function M:onTick()
  self:open() -- first *simulation* callback, not the next 64-tick boundary
  self:checkNetwork()
  self:timeline(self.engine:tick())
  if self.recoveryPending then
    if self.network.syncStatus~=0 then return end
    self:recover()
  end
  self.clock=self.engine:tick()
  self.observedTick=self.clock
  assert(not self.pendingTick,'Native simulation tick did not return to the game loop')
  self.pendingTick={time=self.observedTick,before=require('code/tick-journal').state(self.engine)}
  self.capture.finalRng=self.engine:rngState()
  self.finalResourceData=self.engine:resourceData()
  if self.engine.battle then self.engine.battle:observe() end
  self.finalRngData=self.engine:rngData()
  Trace.onTick(self,true)
  self.boundaryEvents=self.events
end

function M:checkpoint(now)
  return verification.capture(self.engine,self.verificationProfile,now,
    self.capture.finalRng,self.finalRngData,self.finalResourceData)
end

function M:gap(reason,details)
  Trace.gap(self,reason,details)
  if not require('code/multiplayer-session').presentationOrTransport({reason=reason,details=details}) then
    self.recoveryPending=reason
  end
end

function M:recover()
  -- The prior recording ends at its last complete observed boundary. Network
  -- waiting, host migration and replacement-world commands remain in its raw
  -- journal, but never run against the previous world during local playback.
  local previous=self.capture
  local received=self.received
  previous.replayEvents=self.boundaryEvents or 0
  self:stop('native world or player roster changed')
  self:open()
  self.simulationObserved=true
  self.received=received
  self.capture.previousReplay=previous.id
  previous.nextReplay=self.capture.id
  files.seal(previous); files.save(self.capture)
end

function M:afterTick()
  -- Synchronization can return before the simulation hook. Observe that path
  -- too; otherwise a complete replacement could happen between two observed
  -- gameplay ticks without ever marking the previous world as superseded.
  if self.file and core.readInteger(self.engine.base+0xb98)~=self.network.syncStatus then self:checkNetwork() end
  local pending=self.pendingTick
  if not pending then return end -- halted native ticks never reached our start
  self.pendingTick=nil
  assert(self.engine:tick()==pending.time+1,'Native simulation tick advanced unexpectedly')
  local journal=require('code/tick-journal')
  assert(self.tickBytes+journal.SIZE<=M.MAX_TICK_BYTES,'Multiplayer tick journal reached its 128 MiB limit')
  assert(self.tickFile:write(journal.frame(pending.time,pending.before,journal.state(self.engine))))
  self.tickBytes=self.tickBytes+journal.SIZE
  if pending.time%64==0 then assert(self.tickFile:flush()) end
end

function M:beforeCommand()
  Trace.beforeCommand(self)
  self.executing.beforeRng=self.engine:rngState()
end

function M:sealBoundary()
  assert(not self.pendingTick,'Cannot save inside a simulation tick')
  if self.tickFile then assert(self.tickFile:flush()) end
  self.capture.tickBytes=self.tickBytes
  if self.recoveryPending then self.capture.replayEvents=self.boundaryEvents or 0 end
  if self.finalRngData then self.capture.finalRngHash=require('code/native-hash').sha256(self.finalRngData) end
  if self.finalResourceData then self.capture.finalResources=self.engine:resourceState(self.finalResourceData) end
  if self.engine.battle and self.observedTick then
    self.capture.lastObservedTick=self.observedTick
    self.engine.battle:write(self.capture)
  end
end

function M:captureFailure(reason)
  if not self.capture then return end
  self.capture.status='interrupted'; self.capture.reason=reason
  self.capture.bytes=self.bytes; self.capture.lastObservedTick=self.observedTick
  if self.engine.battle and self.observedTick then pcall(self.engine.battle.write,self.engine.battle,self.capture) end
  if self.tickFile then pcall(self.tickFile.close,self.tickFile); self.tickFile=nil end
  files.save(self.capture)
end

function M:rngCall(stream,stack)
  if self.rngAttribution then Trace.rngCall(self,stream,stack) end
end

function M:saveCopy(name)
  assert(self.file and self.capture and not self.executing,'No active multiplayer capture to save')
  assert(self.file:flush())
  self:sealBoundary()
  local copy=files.copyChain(self.capture,name,self.bytes,self.events,self.count,self.observedTick)
  self.lastNamedCopy=copy.displayName
  return copy
end

function M:stop(reason)
  local capture=self.capture
  local hadFile=self.file~=nil
  local wasFailed=self.failed
  local tick=self.observedTick
  if capture and self.tickFile then
    local sealed,sealError=pcall(self.sealBoundary,self)
    local closed,closeError=self.tickFile:close(); self.tickFile=nil
    if not sealed or not closed then wasFailed=true; capture.tickError=tostring(sealError or closeError) end
  end
  local ok,err=pcall(Trace.stop,self,reason)
  if capture and hadFile then
    capture.status=ok and not wasFailed and 'closed' or 'interrupted'
    capture.reason=reason; capture.lastObservedTick=tick
    capture.events=self.events; capture.commands=self.count; capture.bytes=self.bytes
    capture.coverageGaps=self.gaps or 0
    files.save(capture)
    self.lastReplay=files.seal(capture)
    self.lastCapture=capture
  end
  self.capture=nil; self.observedTick=nil; self.pendingTick=nil; self.finalRngData=nil; self.finalResourceData=nil
  assert(ok,err)
end

function M:statusLines()
  if self.failed then return {tr('Capture stopped: %s',tostring(self.failureReason):match('^[^\n]+')),
    tr('Existing capture files are preserved.'),tr('Multiplayer replay playback is not available.')} end
  if self.file then return {tr('Multiplayer capture: tick %d; %d commands',self.observedTick or 0,self.count),
    self.lastNamedCopy and tr('Named copy saved: %s',self.lastNamedCopy)
      or tr('Automatic capture continues until you leave the match.'),
    self.capture and self.capture.world and self.capture.world.status=='failed'
      and tr('Start state unavailable; see capture.json for details.')
      or tr('Saved on this PC. Open Replays in single-player after the match.')} end
  if self.lastCapture then return {tr('Multiplayer capture saved: %s',self.lastCapture.id),
    self.lastCapture.replayStatus=='complete' and tr('Open Replays in single-player to watch this match.')
      or tostring(self.lastCapture.replayReason or tr('Existing capture files are preserved.'))} end
  return {tr('Waiting for the multiplayer match.'),tr('Recordings are saved separately on each PC.')}
end

return M
