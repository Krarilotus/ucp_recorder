-- Read completed native hashes immediately: 14 dwords use a 12-dword stride.
-- Later peer writes can overwrite the last two subtotals in the native table.
local M={}
function M.verify()
  local site=require('code/world-hash-sites').resolve()
  require('code/hook-check').verify(site.guard or site,'Native world-hash observer hook conflicts')
  return site
end
function M.install(trace)
  local site=M.verify()
  core.detourCode(function(registers)
    if registers.ESI==trace.engine.base then trace:observe('worldHash') end
    return registers
  end,site.address,#site.bytes)
  trace.nativeWorldHashes='native-domains-v1'
end
return M
