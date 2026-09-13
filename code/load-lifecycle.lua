-- A native load is not a new lobby start: preserve its RNG and wait until both
-- the file reader and the outer player/menu reconstruction have completed.
local M={}

---@class ReplayLoadLifecycle
---@field recorder table
---@field pending boolean
---@field worldRead boolean
function M.new(recorder)
  return setmetatable({recorder=recorder,pending=false,worldRead=false},{__index=M})
end

function M:cancel()
  self.pending=false; self.worldRead=false
  if self.inputTransition then
    self.inputTransition=false
    self.recorder.input:finish(true)
  end
end

function M:begin()
  if self.recorder.engine.loading then return end -- recorder's own snapshot restore
  self:cancel()
  self.recorder.input:begin()
  self.inputTransition=true
  self.recorder:reset() -- seal the previous world from its last observed boundary
  self.pending=true
end

function M:readComplete(packager)
  local engine=self.recorder.engine
  if self.pending and not engine.loading and packager==engine.sites.packager then
    self.worldRead=true
  end
end

function M:finish()
  local completed=self.pending and self.worldRead
  self:cancel()
  local recorder=self.recorder
  if not completed or recorder.engine.loading or not recorder.autoRecord
    or not recorder.engine:loadedSkirmish() then return end
  recorder:startRecording()
  recorder.manifest.origin='loaded-save'
  recorder:prepareRecording() -- snapshot at the first simulation boundary, no reseeding
end
return M
