-- Temporary identity gate; remaining native profiles are still being migrated.
local profiles = {
  {name = "SHC", header = {80,69,0,0,76,1,4,0,189,147,175,90,0,0,0,0,0,0,0,0,224,0,3,1,11,1,8,0,0,208,25,0,0,240,101,0,0,0,0,0,38,64,24,0,0,16,0,0,0,224,25,0,0,0,64,0}, sha256 = "3bb0a8c1e72331b3a30a5aa93ed94beca0081b476b04c1960e26d5b45387ac5a"},
  {name = "Extreme", header = {80,69,0,0,76,1,4,0,100,173,175,90,0,0,0,0,0,0,0,0,224,0,3,1,11,1,8,0,0,208,25,0,0,160,95,0,0,0,0,0,86,68,24,0,0,16,0,0,0,224,25,0,0,0,64,0}, sha256 = "55648e6b05d67d37a5773fe699bbb17a2d6ad4de1bb9dbded9a21caef82bd7fb"},
}
local M = {}
-- Retain the existing identity gate while the remaining history/scoped
-- profiles are migrated. Runtime lifecycle bindings belong to load-sites.
function M.verify()
  M.profile=nil
  local dos=core.readBytes(0x400000,2)
  local offset=core.readBytes(0x40003c,4)
  assert(dos[1]==0x4d and dos[2]==0x5a and offset[1]==0x18
    and offset[2]==1 and offset[3]==0 and offset[4]==0,
    'Recorder: unsupported executable header')
  local header=core.readBytes(0x400118,56)
  for _,profile in ipairs(profiles) do
    local matches=true
    for i,expected in ipairs(profile.header) do
      if header[i]~=expected then matches=false; break end
    end
    if matches then
      M.profile=profile
      return profile
    end
  end
  error('Recorder: unsupported executable layout; no recorder hooks installed')
end
return M
