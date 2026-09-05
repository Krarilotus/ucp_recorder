-- Opt-in diagnostics; detours retain all original instructions/registers.
local M={}
function M.install(trace)
  local sites=require('code/network-sites')[require('code/native').profile.name]
  for name,site in pairs(sites) do
    local actual=core.readBytes(site.address,#site.bytes)
    for i,byte in ipairs(site.bytes) do
      assert(actual[i]==byte,'Multiplayer observer hook conflicts at '..name)
    end
  end
  for name,site in pairs(sites) do
    local source=name
    local event=name=='localTimed' and 'locallyQueuedCommand' or 'immediateCommand'
    core.detourCode(function(registers)
      trace:observe(event,source)
      return registers
    end,site.address,#site.bytes)
  end
end
return M
