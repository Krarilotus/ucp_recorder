-- Recorder observes/restores the native RNG; it never substitutes a generator.
local M={}
local patterns={
  initialization='B9 ? ? ? ? E8 ? ? ? ? 6A 09 B9 ? ? ? ? E8 ? ? ? ? 6A 09 B9 ? ? ? ? 89 3D ? ? ? ? E8 ? ? ? ? 6A 34 B9 ? ? ? ? E8 ? ? ? ? 83 3D ? ? ? ? 63 75 1E',
  stream1='8B 81 4C 9C 00 00 66 8B 54 41 08 83 C0 01 3D 20 4E 00 00 66 89 11 89 81 4C 9C 00 00 7C 0A C7 81 4C 9C 00 00 00 00 00 00 C3',
  stream2='8B 81 48 9C 00 00 66 8B 54 41 08 83 C0 01 3D 20 4E 00 00 66 89 51 02 89 81 48 9C 00 00 7C 0A C7 81 48 9C 00 00 00 00 00 00 C3',
}
local seedPattern='56 6A 00 8B F1 E8 ? ? ? ? 83 C4 04 89 46 04 5E C3'
local bindings

local function context(address,pattern,name)
  local tokens={}
  for token in pattern:gmatch('%S+') do tokens[#tokens+1]=token end
  local bytes=core.readBytes(address,#tokens)
  for i,token in ipairs(tokens) do
    assert(token=='?' or bytes[i]==tonumber(token,16),'Modified native RNG '..name)
  end
  return {address=address,bytes=bytes}
end

function M.resolve()
  if bindings then return bindings end
  local sites={}
  for _,name in ipairs({'initialization','stream1','stream2'}) do
    local pattern=patterns[name]
    local ok,address=pcall(core.AOBScan,pattern)
    assert(ok and type(address)=='number' and address>0,'Cannot resolve native RNG '..name)
    local second=core.scanForAOB(pattern,address+1)
    assert(second==nil or second==0,'Ambiguous native RNG '..name)
    sites[name]=context(address,pattern,name)
  end
  local entry=sites.initialization.address
  local state=core.readInteger(entry+1)
  require('code/validation').integer(state,0x10000,0x7fffffff-0x9c50,'Native RNG state')
  local seed=entry+10+core.readInteger(entry+6)
  require('code/validation').integer(seed,0x10000,0x7fffffff-18,'Native RNG seed entry')
  context(seed,seedPattern,'seed entry')
  -- Two consecutive native lobby commands must use Protocol's verified handler.
  local commands=modules.protocol:getNativeCommandInterface()
  assert(core.readInteger(entry+25)==commands.handler and core.readInteger(entry+43)==commands.handler,
    'Native RNG initialization has a different command owner')
  bindings={state=state,streams={sites.stream1,sites.stream2}}
  return bindings
end
return M
