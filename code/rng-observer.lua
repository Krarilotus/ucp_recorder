-- Attribution only. Original RNG instructions execute unchanged after the detour.
local M={}
function M.verify()
  local sites={}
  -- Check every entry before installing any hook.
  for stream,entry in ipairs(require('code/rng-bindings').resolve().streams) do
    require('code/hook-check').verify(entry,'RNG diagnostic hook conflicts at stream '..stream)
    sites[stream]={stream=stream,address=entry.address,bytes=core.readBytes(entry.address,6)}
  end
  return sites
end
function M.install(trace)
  local sites=M.verify()
  for _,site in ipairs(sites) do
    local stream=site.stream
    core.detourCode(function(registers)
      if registers.ECX==trace.engine.rng then
        trace:observe('rngCall',stream,registers.ESP)
      end
      return registers
    end,site.address,#site.bytes)
  end
end
return M
