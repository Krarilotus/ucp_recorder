-- Recorder owns world replacement. Consumers may cancel local input here,
-- but must not advance, pause, load, or mutate the replay from an observer.
local M={VERSION=1}
M.__index=M

---@class RecorderInputState
---@field generation integer Changes before and after every world transition.
---@field blocked boolean No live extension input is allowed.
---@field version integer API format, independent of the replay file format.
function M.new(session)
  return setmetatable({session=session,generation=0,depth=0,failed=false,observers={}},M)
end

function M:read()
  local s=self.session
  return {version=M.VERSION,generation=self.generation,
    blocked=self.failed or self.depth>0 or s.mode=='play' or s.engine.loading==true
      or s.engine.offline~=nil and s.engine.offline~=false,
    mode=s.mode,status=s.status}
end

function M:observe(callback)
  assert(type(callback)=='function','Input observer must be a function')
  local entry={callback=callback}
  self.observers[#self.observers+1]=entry
  return function() entry.callback=nil end
end

function M:notify()
  self.generation=self.generation+1
  local failure
  for _,entry in ipairs(self.observers) do
    if entry.callback then
      local ok,reason=pcall(entry.callback)
      if not ok then failure=failure or reason end
    end
  end
  if failure then self.failed=true; error(failure,0) end
end

function M:begin()
  self.depth=self.depth+1
  self:notify() -- Already blocked; all local holds must be released before mutation.
end

function M:finish(ok)
  assert(self.depth>0,'Unbalanced recorder input transition')
  if not ok then self.failed=true end -- An uncertain world cannot regain live input.
  self.depth=self.depth-1
  self:notify()
end

function M:transition(callback)
  self:begin()
  local ok,reason=xpcall(callback,debug.traceback)
  self:finish(ok)
  assert(ok,reason)
end

return M
