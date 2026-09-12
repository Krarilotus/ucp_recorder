-- Scheduling only. Capture/publication owns committing a completed boundary.
-- Dates are elapsed game calendar months; wall time and viewer speed never enter.
local integer=require('code/validation').integer
local M={LOCAL_MONTHS=12,EMBEDDED_MONTHS=300}

---@class ReplaySnapshotCadence
---@field origin integer
---@field interval integer
---@field nextMonth integer
local Cadence={}

---@param year integer
---@param month integer Zero-based native calendar month.
---@return integer
function M.month(year,month)
  return integer(year,-100000,100000,'snapshot year')*12
    +integer(month,0,11,'snapshot month')
end

function M.new(origin,interval)
  integer(origin,-1200000,1200011,'snapshot origin')
  integer(interval,1,1200000,'snapshot interval')
  return setmetatable({origin=origin,interval=interval,nextMonth=origin+interval},{__index=Cadence})
end

function Cadence:due(month)
  return month>=self.nextMonth
end

function Cadence:commit(month)
  assert(self:due(month),'Snapshot precedes its next calendar boundary')
  -- A calendar jump produces one current snapshot, never several copies of
  -- the same world. Replaying old years does not repeat completed captures.
  self.nextMonth=self.origin+(math.floor((month-self.origin)/self.interval)+1)*self.interval
end

return M
