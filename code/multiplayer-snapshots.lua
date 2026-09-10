-- Periodic peer-local worlds and their journal-to-replay bookmark conversion.
-- The network observer owns admission; snapshot-store owns files and hashes;
-- world-capture owns read-only native/extension state. Never invoke native save.
local cadence=require('code/snapshot-cadence')
local storage=require('code/snapshot-store')
local platform=require('code/platform')
local validation=require('code/validation')
local M={}
local Recording={}

function M.new(trace,origin)
  local month=trace.engine:calendarMonth()
  trace.capture.snapshotOriginMonth=origin or month
  local schedule=cadence.new(origin or month,cadence.EMBEDDED_MONTHS)
  -- A recovery segment already has a starting world at this date. Keep the
  -- original cadence, but do not immediately duplicate that starting snapshot.
  if schedule:due(month) then schedule:commit(month) end
  return setmetatable({trace=trace,cadence=schedule},{__index=Recording})
end

function Recording:observe()
  local trace=self.trace
  if self.disabled then return end
  local month=trace.engine:calendarMonth()
  if not self.cadence:due(month) then return end
  if trace.recoveryPending or trace.network.syncStatus~=0 or trace.executing or trace.pendingTick
    or trace.engine.executing or trace.engine:commandsPending() then return end
  local capture=trace.capture
  if #(capture.snapshots or {})>=storage.MAX_POINTS then self.disabled=true; return end
  local root=trace.path..'/snapshots'
  local ok,reason=pcall(platform.mkdir,root)
  if not ok then self.disabled=true; print('[recorder] Optional MP snapshots disabled: '..tostring(reason)); return end
  local point,reason=storage.capture(trace.engine,root..'/'..trace.engine:tick(),month,trace.count,nil,
    function(filename) return require('code/world-capture').writeSnapshot(filename,trace.engine) end)
  if not point then self.disabled=true; print('[recorder] Optional MP snapshots disabled: '..tostring(reason)); return end
  point.traceSequence=trace.events
  capture.snapshots=capture.snapshots or {}; capture.snapshots[#capture.snapshots+1]=point
  self.cadence:commit(month)
  local published,err=pcall(require('code/capture-files').save,capture)
  if not published then
    self.disabled=true; print('[recorder] MP snapshot metadata deferred until sealing: '..tostring(err))
  end
end

local function eligible(capture)
  local points={}
  local bounds={startTick=capture.startTick,lastTick=capture.lastObservedTick,commandCount=capture.commands}
  if type(capture.snapshots)~='table' or #capture.snapshots>storage.MAX_POINTS then return points end
  local previousTick,previousSequence=capture.startTick,-1
  for _,point in ipairs(capture.snapshots) do
    local ok=pcall(function()
      storage.validateState(point,bounds)
      validation.integer(point.traceSequence,0,capture.events,'snapshot trace position')
      assert(point.tick>previousTick and point.traceSequence>=previousSequence,'Unordered multiplayer snapshots')
    end)
    if ok and (not capture.replayEvents or point.traceSequence<=capture.replayEvents) then
      points[#points+1]=point; previousTick=point.tick; previousSequence=point.traceSequence
    end
  end
  return points
end

-- Invoked at header/record boundaries by the existing single-pass converter.
-- There is no second journal scan and no per-tick snapshot index in the replay.
function M.indexer(capture,manifest,commands,checkpoints)
  local points=eligible(capture)
  if #points==0 then return end
  local index=1
  return function(sequence,time)
    while points[index] and points[index].traceSequence==sequence do
      local point=points[index]; index=index+1
      if point.commands==manifest.commandCount and point.tick>=time then
        local converted={}; for key,value in pairs(point) do converted[key]=value end
        converted.traceSequence=nil
        converted.bookmark={positions={commandsFile=assert(commands:seek()),rngFile=assert(checkpoints:seek()),
          infoFile=0,tickFile=(point.tick-manifest.startTick)*require('code/tick-journal').SIZE}}
        manifest.snapshots=manifest.snapshots or {}; manifest.snapshots[#manifest.snapshots+1]=converted
      end
    end
  end
end

-- Named multiplayer prefixes copy only embedded worlds, including earlier
-- recovery segments. Local playback cache never enters this owner.
function M.copy(source,target)
  local points=eligible(target) -- the caller supplies the current flushed prefix counts
  target.snapshots=nil
  for _,point in ipairs(points) do
    if point.tick<=target.lastObservedTick then
      local root=target.path..'/snapshots'; local to=root..'/'..point.tick
      local ok,reason=pcall(function()
        platform.mkdir(root)
        storage.copyWorld(point,source.path..'/snapshots/'..point.tick,to)
      end)
      if ok then
        target.snapshots=target.snapshots or {}; target.snapshots[#target.snapshots+1]=point
      else
        storage.remove(to)
        print('[recorder] Optional MP restore point omitted from named copy: '..tostring(reason))
      end
    end
  end
end

return M
