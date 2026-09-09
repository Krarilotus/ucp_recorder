---Presentation controls for an active replay. Recording and network state are
---owned by the session/engine; the menu never writes native memory directly.
---@class ReplayPlaybackControls
---@field session table
local Controls={SPEEDS={20,40,60,90,100,150,200,300,500,750,1000}}
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

-- Main keyboard and numeric keypad. Consume the generated character too so a
-- viewer shortcut cannot also reach the native gameplay command producer.
function Controls:key(message,key)
  local direction=(key==187 or key==107) and 1 or (key==189 or key==109) and -1
  local character=message==0x102 and (key==43 or key==45 or key==61 or key==95 or key==42)
  if not direction and not character then return false end
  if message~=0x100 and message~=0x101 and message~=0x102 then return false end
  if not self:available() then return false end
  if message==0x100 and direction then self:stepSpeed(direction) end
  return true
end

return Controls
