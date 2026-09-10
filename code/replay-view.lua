-- A view is a presentation choice. The native actor, queue and replay manifest
-- never change. Each native renderer reads the selected player's live statistics;
-- the original local slot is restored before that rendering scope returns.
local native=require('code/native')
local M={}
function M.new(recorder)
 return setmetatable({recorder=recorder},{__index=M})
end
function M:available()
 local r=self.recorder
 return r.mode=='play' and r.active and r.manifest and r.engine:localSession()
   and (r.status=='playing' or r.status=='finished' or r.status=='error')
end
function M:players()
 if not self:available() then return {} end
 self:player()
 if self.roster then return self.roster end
 local r=self.recorder
 local state=r.engine:networkState()
 local result={}
 for slot=1,8 do
  if slot==r.manifest.player or state.roster[slot].kind~='empty' then result[#result+1]=slot end
 end
 if self.selected and self.selected~=r.manifest.player and state.roster[self.selected].kind=='empty' then
  self.selected=nil
 end
 self.roster=result
 return self.roster
end
function M:player()
 local r=self.recorder
 local session=r.snapshots or r.manifest
 if self.session~=session then self.session=session; self.selected=nil; self.roster=nil end
 if self.manifest~=r.manifest then self.manifest=r.manifest; self.roster=nil end
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
