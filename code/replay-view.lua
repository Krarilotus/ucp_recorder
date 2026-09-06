-- A view is a presentation choice. The native actor, queue and replay manifest
-- never change. The original local slot is restored before menu rendering returns.
local native=require('code/native')
local M={}
function M.new(recorder)
 return setmetatable({recorder=recorder},{__index=M})
end
function M:available()
 local r=self.recorder
 return r.mode=='play' and r.active and r.manifest and r.engine:singlePlayer()
   and (r.status=='playing' or r.status=='finished' or r.status=='error')
end
function M:players()
 if not self:available() then return {} end
 local r=self.recorder
 local state=r.engine:networkState()
 local result={}
 for slot=1,8 do
  if slot==r.manifest.player or state.roster[slot].kind~='empty' then result[#result+1]=slot end
 end
 return result
end
function M:player()
 local r=self.recorder
 if self.session~=r.manifest then self.session=r.manifest; self.selected=nil end
 return self.selected or (r.manifest and r.manifest.player)
end
function M:select(slot)
 assert(self:available(),'Player viewing is only available during replay')
 self:player() -- discard a selection from an earlier replay
 for _,player in ipairs(self:players()) do
  if slot==player then self.selected=slot; return end
 end
 error('Player is not present in this replay')
end
function M:render(callback)
 if not self:available() then return callback() end
 local slot=self:player()
 local address=native.addr(0x1a275dc)
 local previous=core.readInteger(address)
 core.writeInteger(address,slot)
 local ok,result=xpcall(callback,debug.traceback)
 core.writeInteger(address,previous)
 assert(ok,result)
 return result
end
return M
