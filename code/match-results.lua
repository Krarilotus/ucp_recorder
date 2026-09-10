-- The native victory/defeat view ends simulation before presenting statistics.
-- Seal at that transition. Link only a record actually inserted by SKMasters;
-- never infer identity from a map name, date, score, or an old history entry.
local native=require('code/native')
local store=require('code/sessions')
local stats=require('code/battle-statistics')
local M={}
M.sites={
  SHC={address=0x4d534d,bytes={129,61,76,98,223,0,250,0,0,0},records=0xdf6250},
  Extreme={address=0x4d56dd,bytes={129,61,228,98,223,0,250,0,0,0},records=0xdf62e8},
}

function M.verify()
  local site=assert(M.sites[native.profile.name])
  require('code/hook-check').verify(site,'Native battle result insertion conflicts')
  return site
end

function M.new(recorder,site)
  local self=setmetatable({recorder=recorder},{__index=M})
  core.detourCode(function(registers)
    recorder:guard(function()
      if not self.pending then return end
      local index=registers.EBX
      assert(index>=0 and index<250,'Native result index is invalid')
      local manifest=self.pending
      self.pending=nil
      manifest.nativeBattleHash=sha.sha256(core.readString(site.records+index*stats.SIZE,stats.SIZE))
      store.save(manifest)
    end)
    return registers
  end,site.address,#site.bytes)
  return self
end

function M:onMenuView(view)
  local r=self.recorder
  if r.engine.loading then return end
  if view~=29 and view~=30 then self.pending=nil; return end
  if r.mode=='play' then return end -- viewer results never finish a live capture
  if r.mode=='record' and r.active then
    local manifest=r.manifest
    r:reset()
    if manifest.status=='complete' then self.pending=manifest end
  else
    local trace=r.engine.trace
    if trace and trace.capture then
      local id=trace.capture.id
      trace:observe('stop','native match results')
      if trace.lastReplay and trace.lastReplay.id==id and trace.lastReplay.status=='complete' then
        self.pending=trace.lastReplay
      end
    end
  end
end
return M
