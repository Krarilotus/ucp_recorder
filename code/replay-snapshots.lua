-- Session-owned restore points. Only capture at the recorder's pre-clock
-- boundary; UI input merely queues a seek for the outer menu-update boundary.
local cadence=require('code/snapshot-cadence')
local storage=require('code/snapshot-store')
local store=require('code/sessions')
local M={MAX_CACHE_BYTES=256*1024*1024}

---@class ReplaySnapshots
---@field session table
---@field entries table[] Locally generated snapshots, never exported.
---@field bytes integer
local Snapshots={}

function M.new(session,ready)
  local origin=session.manifest.snapshotOriginMonth or session.engine:calendarMonth()
  local self=setmetatable({session=session,ready=ready,entries={},bytes=0,prepared={},cadences={},
    cadence=cadence.new(origin,session.mode=='record' and cadence.EMBEDDED_MONTHS or cadence.LOCAL_MONTHS)},
    {__index=Snapshots})
  if ready then
    self.timeline=require('code/replay-timeline').new(ready.manifest,ready.worlds)
    self.prepared[ready.manifest.id]=ready
    self.cadences[ready.manifest.id]=self.cadence
  end
  return self
end

function Snapshots:close()
  if self.pending then self.pending:cancel(); self.pending=nil end
  for _,entry in ipairs(self.entries) do
    local ok,reason=storage.remove(entry.path)
    if not ok then print('[recorder] Cannot remove local snapshot: '..tostring(reason)) end
  end
  self.entries={}; self.bytes=0
end

function Snapshots:observe()
  local r=self.session
  if self.disabled or self.pending or r.status~='playing' and r.status~='recording' then return end
  local month=r.engine:calendarMonth()
  if not self.cadence:due(month) then return end
  -- The same deadline can be encountered again after rewinding. Keep the
  -- existing point rather than save the same world a second time.
  if r.engine:commandsPending() or r.engine.executing or r.pendingTick then return end
  if r.mode=='record' and #(r.manifest.snapshots or {})>=storage.MAX_POINTS then self.disabled=true; return end
  if r.mode=='play' then
    local year=math.floor((month-self.cadence.origin)/cadence.LOCAL_MONTHS)
    for _,entry in ipairs(self.entries) do
      if entry.id==r.manifest.id and math.floor((entry.point.month-self.cadence.origin)/cadence.LOCAL_MONTHS)==year then
        self.cadence:commit(month); return
      end
    end
    -- Reserve the largest supported point before saving. Failed eviction must
    -- not silently exceed the cache budget or repeatedly write more files.
    while self.bytes+storage.MAX_WORLD+0x9c50>M.MAX_CACHE_BYTES do
      local oldest=self.entries[1]
      local removed,reason
      if oldest then removed,reason=storage.remove(oldest.path) end
      if not removed then
        self.disabled=true
        print('[recorder] Snapshot cache is full: '..tostring(reason or 'insufficient capacity'))
        return
      end
      table.remove(self.entries,1); self.bytes=self.bytes-oldest.point.bytes-0x9c50
    end
  end
  local available,path=pcall(function()
    if r.mode=='record' then
      local root=store.path(r.manifest.id)..'/snapshots'
      require('code/platform').mkdir(root)
      return root..'/'..r.engine:tick()
    end
    return storage.cachePath()
  end)
  if not available then
    self.disabled=true; print('[recorder] Optional snapshot directory unavailable: '..tostring(path)); return
  end
  local commands=r.mode=='record' and r.manifest.commandCount or r.playedCommands
  local manifest=r.manifest
  local job,reason=require('code/snapshot-jobs').start(r.engine,path,month,commands,r:bookmark(),function(point,err)
    self.pending=nil
    if not point then self.disabled=true; print('[recorder] Optional snapshot failed: '..tostring(err)); return end
    if r.mode=='record' then
      manifest.snapshots=manifest.snapshots or {}; manifest.snapshots[#manifest.snapshots+1]=point
    else
      self.entries[#self.entries+1]={point=point,path=path,id=manifest.id}
      self.bytes=self.bytes+point.bytes+0x9c50
    end
  end)
  if not job then
    if reason=='busy' then return end
    self.disabled=true
    print('[recorder] Optional snapshot capture disabled: '..tostring(reason))
    return
  end
  self.pending=job
  self.cadence:commit(month)
end

function Snapshots:nearest(tick,manifest)
  manifest=manifest or self.session.manifest
  local best
  local embedded=manifest.snapshots
  if type(embedded)~='table' or #embedded>storage.MAX_POINTS then embedded={} end
  for _,point in ipairs(embedded) do
    if pcall(storage.validate,point,manifest) and point.tick<=tick and (not best or point.tick>best.point.tick) then
      best={point=point,path=storage.path(manifest,point),id=manifest.id}
    end
  end
  for _,entry in ipairs(self.entries) do
    if entry.id==manifest.id and entry.point.tick<=tick and (not best or entry.point.tick>best.point.tick) then best=entry end
  end
  return best
end

function Snapshots:request(fraction)
  local r=self.session
  assert(r.mode=='play' and r.active and (r.status=='playing' or r.status=='finished'),
    'Replay seeking is unavailable')
  self.requestedId,self.requested=self.timeline:at(fraction)
  self.resume=r.status=='playing' and not r.engine:isPaused()
end

function Snapshots:advance()
  if not self.requested then return end
  local r=self.session; local target,id=self.requested,self.requestedId
  self.requested=nil; self.requestedId=nil
  if id==r.manifest.id and r.status=='playing' and target>=r.engine:tick() then
    local nextPoint=self:nearest(target)
    if not nextPoint or nextPoint.point.tick<=r.engine:tick() then
      -- The active world is already closer than every restore point. Continue
      -- the normal simulation instead of loading and redoing completed work.
      self.error=nil; self.target=target; r.engine:setPaused(false)
      return
    end
  end
  local preparation=require('code/replay-preparation')
  local valid,ready,cached=pcall(function()
    local ready=self.prepared[id] or preparation.segment(self.ready,id)
    local point=self:nearest(target,ready.manifest)
    -- Preparation only reads files. Validate before dropping the active world.
    local cached
    if point then
      local ok,result=pcall(storage.prepare,ready.manifest,point.point,point.path)
      if ok then cached=result
      else print('[recorder] Restore point unavailable; seeking from the starting save: '..tostring(result)) end
    end
    if not cached then preparation.checkStartingState(ready) end
    return ready,cached
  end)
  if not valid then
    self.error=tostring(ready)
    print('[recorder] Seek cancelled; active replay retained: '..self.error)
    return
  end
  self.error=nil
  local resume=self.resume
  self:load(ready,cached)
  self.target=target; self.resume=resume
  r.engine:setPaused(false)
end

function Snapshots:load(ready,cached)
  local r=self.session
  if self.pending then self.pending:cancel(); self.pending=nil end
  r.snapshots=nil -- preserve this cache across the internal reset/load
  local ok,reason=xpcall(function()
    r.input:transition(function()
      r:reset()
      r:startPlayback(ready.manifest.id,nil,ready,cached)
    end)
  end,debug.traceback)
  if r.snapshots then r.snapshots:close() end
  r.snapshots=self
  assert(ok,reason)
  self.prepared[ready.manifest.id]=ready
  local previous=self.cadences[ready.manifest.id]
  self.cadence=cadence.new(previous and previous.origin or
    ready.manifest.snapshotOriginMonth or r.engine:calendarMonth(),cadence.LOCAL_MONTHS)
  self.cadences[ready.manifest.id]=self.cadence
end

function Snapshots:transition(id)
  local ready=self.prepared[id] or require('code/replay-preparation').segment(self.ready,id)
  require('code/replay-preparation').checkStartingState(ready)
  self:load(ready)
end

function Snapshots:progress(tick)
  return self.timeline:position(self.session.manifest.id,tick or self.session.engine:tick())
end

-- Called before reading the target tick's RNG journal. Halting this invocation
-- must not create a pending multiplayer tick that falsely expects clock+1.
function Snapshots:atBoundary(now)
  if not self.target or now<self.target then return false end
  assert(now==self.target,'Replay seek passed its target')
  self.target=nil
  local r=self.session
  if self.resume or now==r.manifest.lastTick then return false end
  r.engine:pause(); self.stopped=true
  core.writeInteger(r.halt,1)
  return true
end

function Snapshots:afterTick()
  if not self.stopped then return false end
  self.stopped=nil
  -- Viewer pause owns future admission. The halt bit was only for the current
  -- pre-clock invocation; ordinary unpause must continue the replay afterward.
  core.writeInteger(self.session.halt,0)
  return true
end

return M
