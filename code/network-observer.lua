-- Opt-in diagnostics; detours retain all original instructions/registers.
local M={}
function M.verify()
  local sites=require('code/network-sites')[require('code/native').profile.name]
  for name,site in pairs(sites) do
    require('code/hook-check').verify(site,'Multiplayer observer hook conflicts at '..name)
  end
  return sites
end
function M.install(trace)
  local sites=M.verify()
  for name,site in pairs(sites) do
    local source=name
    local event=name=='systemMessage' and 'systemMessage' or 'immediateCommand'
    core.detourCode(function(registers)
      trace:observe(event,source)
      return registers
    end,site.address,#site.bytes)
  end
end
return M
