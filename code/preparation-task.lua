---A cooperative, read-only preparation task owned by the replay browser.
---Cancellation resumes the worker so file/hash owners run their normal cleanup.
local M={BUDGET_MS=12,MAX_STEPS=64}
M.__index=M
function M.new(action,clock)
  local self=setmetatable({clock=clock,status='pending',workMs=0},M)
  self.thread=coroutine.create(function()
    return action(function(message)
      self.message=message
      coroutine.yield()
      assert(not self.cancelled,'Replay preparation cancelled')
    end)
  end)
  return self
end
function M:cancel() self.cancelled=true end
function M:step()
  if self.status~='pending' or self.running then return end
  self.running=true
  local started=self.clock()
  self.started=self.started or started
  for _=1,M.MAX_STEPS do
    local ok,value=coroutine.resume(self.thread)
    if not ok or coroutine.status(self.thread)=='dead' then
      self.status=self.cancelled and 'cancelled' or (ok and 'ready' or 'failed')
      if ok then self.result=value else self.error=tostring(value) end
      self.thread=nil
      break
    end
    if (self.clock()-started)%4294967296>=M.BUDGET_MS then break end
  end
  local finished=self.clock()
  self.workMs=self.workMs+(finished-started)%4294967296
  self.elapsedMs=(finished-self.started)%4294967296
  self.running=false
end
return M
