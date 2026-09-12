-- Recorder observes/restores the native RNG; it never substitutes a generator.
local M={}
local patterns={
  initialization='B9 ? ? ? ? E8 ? ? ? ? 6A 09 B9 ? ? ? ? E8 ? ? ? ? 6A 09 B9 ? ? ? ? 89 3D ? ? ? ? E8 ? ? ? ? 6A 34 B9 ? ? ? ? E8 ? ? ? ? 83 3D ? ? ? ? 63 75 1E',
  stream1='8B 81 4C 9C 00 00 66 8B 54 41 08 83 C0 01 3D 20 4E 00 00 66 89 11 89 81 4C 9C 00 00 7C 0A C7 81 4C 9C 00 00 00 00 00 00 C3',
  stream2='8B 81 48 9C 00 00 66 8B 54 41 08 83 C0 01 3D 20 4E 00 00 66 89 51 02 89 81 48 9C 00 00 7C 0A C7 81 48 9C 00 00 00 00 00 00 C3',
}
local seedPattern='56 6A 00 8B F1 E8 ? ? ? ? 83 C4 04 89 46 04 5E C3'
local bindings,seedAddress

function M.resolve()
  if bindings then return bindings end
  local sites={}
  local check=require('code/hook-check')
  for _,name in ipairs({'initialization','stream1','stream2'}) do
    local pattern=patterns[name]
    sites[name]=check.resolve(pattern,'Recorder native RNG '..name)
  end
  local entry=sites.initialization.address
  local state=core.readInteger(entry+1)
  require('code/validation').integer(state,0x10000,0x7fffffff-0x9c50,'Native RNG state')
  local seed=entry+10+core.readInteger(entry+6)
  require('code/validation').integer(seed,0x10000,0x7fffffff-18,'Native RNG seed entry')
  -- The optional seed hook occupies these six middle bytes. Its untouched
  -- instructions are required only when useFixedSeed is enabled.
  check.context(seed,'56 6A 00 8B F1 E8 ? ? ? ? ? ? ? ? ? ? 5E C3','Recorder RNG seed wrapper')
  -- Two consecutive native lobby commands must use Protocol's verified handler.
  local commands=modules.protocol:getNativeCommandInterface()
  assert(core.readInteger(entry+25)==commands.handler and core.readInteger(entry+43)==commands.handler,
    'Native RNG initialization has a different command owner')
  bindings={state=state,initialization=sites.initialization,
    streams={sites.stream1,sites.stream2}}
  seedAddress=seed
  return bindings
end
function M.seed()
  M.resolve()
  return require('code/hook-check').context(seedAddress,seedPattern,'Recorder optional seed hook')
end
return M
