-- Attribution only. Original RNG instructions execute unchanged after the detour.
local native=require('code/native')
local M={}
function M.install(trace)
  local sites={
    {stream=1,address=native.addr(0x46a800),bytes={139,129,76,156,0,0}},
    {stream=2,address=native.addr(0x46a7d0),bytes={139,129,72,156,0,0}},
  }
  -- Check every entry before installing any hook.
  for _,site in ipairs(sites) do
    local actual=core.readBytes(site.address,#site.bytes)
    for i,byte in ipairs(site.bytes) do
      assert(actual[i]==byte,'RNG diagnostic hook conflicts at stream '..site.stream)
    end
  end
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
