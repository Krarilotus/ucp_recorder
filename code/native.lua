-- UCP owns game-version detection. Capability owners verify their native
-- contexts; the actual executable digest identifies recordings, not addresses.
local M={}
function M.verify()
  M.profile=nil
  local version=data and data.version
  assert(version and tonumber(version.getGameVersionMajor())==1
    and tonumber(version.getGameVersionMinor())==41,
    'Recorder requires UCP-supported Crusader or Crusader Extreme 1.41')
  local name=version.isExtreme() and 'Extreme' or 'SHC'
  local path=require('code/platform').identity().executable
  local digest=require('code/native-hash').file(path,64*1024*1024)
  require('code/validation').hash(digest,'executable identity')
  M.profile={name=name,sha256=digest}
  return M.profile
end
return M
