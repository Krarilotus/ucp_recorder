-- Durable, read-only capture on each peer. This is not offline playback.
local Trace=require('code/multiplayer-trace')
local files=require('code/capture-files')
local store=require('code/sessions')
local tr=require('code/locale').text
local M={ROOT='ucp/multiplayer-recordings',MAX_BYTES=256*1024*1024}
setmetatable(M,{__index=Trace})

function M.new(engine,config)
  -- Full-match persistence must never inherit a bounded diagnostic window.
  local self=Trace.new(engine,{})
  self.root=M.ROOT
  self.fileMode='wb' -- byte offsets must not change through Windows CRLF translation
  self.rngAttribution=config and config.multiplayerDiagnostics==true
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
  Trace.open(self)
  self.capture=files.begin(self.path,self.engine,store.settings())
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
  end
  self.clock=now
end

function M:record(event)
  self:timeline(event.time)
  Trace.record(self,event)
end

function M:onTick()
  self:open() -- first *simulation* callback, not the next 64-tick boundary
  self:timeline(self.engine:tick())
  self.observedTick=self.engine:tick()
  Trace.onTick(self)
end

function M:captureFailure(reason)
  if not self.capture then return end
  self.capture.status='interrupted'; self.capture.reason=reason
  self.capture.bytes=self.bytes; self.capture.lastObservedTick=self.observedTick
  files.save(self.capture)
end

function M:rngCall(stream,stack)
  if self.rngAttribution then Trace.rngCall(self,stream,stack) end
end

function M:saveCopy(name)
  assert(self.file and self.capture and not self.executing,'No active multiplayer capture to save')
  assert(self.file:flush())
  local copy=files.copy(self.capture,name,self.bytes,self.events,self.count,self.observedTick)
  self.lastNamedCopy=copy.displayName
  return copy
end

function M:stop(reason)
  local capture=self.capture
  local hadFile=self.file~=nil
  local wasFailed=self.failed
  local tick=self.observedTick
  local ok,err=pcall(Trace.stop,self,reason)
  if capture and hadFile then
    capture.status=ok and not wasFailed and 'closed' or 'interrupted'
    capture.reason=reason; capture.lastObservedTick=tick
    capture.events=self.events; capture.commands=self.count; capture.bytes=self.bytes
    capture.coverageGaps=self.gaps or 0
    files.save(capture)
    self.lastCapture=capture
  end
  self.capture=nil; self.observedTick=nil
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
      or tr('Saved on this PC. Offline playback is not available yet.')} end
  if self.lastCapture then return {tr('Multiplayer capture saved: %s',self.lastCapture.id),
    tr('Saved on this PC. Offline playback is not available yet.')} end
  return {tr('Waiting for the multiplayer match.'),tr('Saved on this PC. Offline playback is not available yet.')}
end

return M
