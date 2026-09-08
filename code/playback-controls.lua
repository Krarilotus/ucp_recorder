---Presentation controls for an active replay. Recording and network state are
---owned by the session/engine; the menu never writes native memory directly.
---@class ReplayPlaybackControls
---@field session table
local Controls={SPEEDS={20,40,60,90,150,200,300}}
Controls.__index=Controls

---@param session table
---@return ReplayPlaybackControls
function Controls.new(session)
  return setmetatable({session=session},Controls)
end

---@return boolean
function Controls:available()
  local session=self.session
  return session.mode=='play' and session.active==true and session.status=='playing'
    and session.engine:localSession()
end

---@return boolean
function Controls:paused()
  return self.session.engine:isLogicallyPaused()
end

---@return integer
function Controls:speed()
  return self.session.engine:presentationSpeed()
end

---@param direction -1|1
---@return integer|nil
function Controls:nextSpeed(direction)
  assert(direction==-1 or direction==1,'Invalid replay speed direction')
  local current=self:speed()
  if direction==1 then
    for _,speed in ipairs(self.SPEEDS) do if speed>current then return speed end end
  else
    for i=#self.SPEEDS,1,-1 do if self.SPEEDS[i]<current then return self.SPEEDS[i] end end
  end
end

function Controls:togglePause()
  assert(self:available(),'Playback controls are not active')
  self.session.engine:setPaused(not self:paused())
end

---@param direction -1|1
function Controls:stepSpeed(direction)
  assert(self:available(),'Playback controls are not active')
  local value=self:nextSpeed(direction)
  if value then self.session.engine:setPresentationSpeed(value) end
end

return Controls
