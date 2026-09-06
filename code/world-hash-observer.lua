-- Read completed native hashes immediately: 14 dwords use a 12-dword stride.
-- Later peer writes can overwrite the last two subtotals in the native table.
local M={}
function M.install(trace)
  local site=require('code/world-hash-sites')[require('code/native').profile.name]
  local actual=core.readBytes(site.address,#site.bytes)
  for i,byte in ipairs(site.bytes) do
    assert(actual[i]==byte,'Native world-hash observer hook conflicts')
  end
  core.detourCode(function(registers)
    if registers.ESI==trace.engine.base then trace:observe('worldHash') end
    return registers
  end,site.address,#site.bytes)
  trace.nativeWorldHashes='native-domains-v1'
end
return M
