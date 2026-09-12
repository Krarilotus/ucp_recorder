-- Recorder observes distinct instructions immediately before Protocol's dispatch
-- hooks. The discovery contexts end before those hooks and remain unmodified.
local contexts={
  systemMessage={offset=0,size=5,pattern='8B 07 83 F8 03 0F 84 9B 01 00 00 83 F8 05 75 20 C7 86 ? ? ? ? 3D 00 00 00 8B 57 08 52 8B CE E8 ? ? ? ? 50 E8 ? ? ? ? E9 76 01 00 00 83 F8 31 0F 84 6D 01 00 00 3D 01 01 00 00'},
  remoteImmediate={offset=54,size=7,pattern='89 86 ? ? ? ? 89 AE 64 A8 07 00 89 AE 60 A8 07 00 89 AE 5C A8 07 00 89 AE 58 A8 07 00 89 AE 54 A8 07 00 89 AE 50 A8 07 00 89 AE 28 D8 02 00 89 AE ? ? ? ? 0F BE 87 84 C6 03 00'},
  localImmediate={offset=72,size=8,pattern='8B 8E 24 D8 02 00 8B 96 A4 06 00 00 69 C9 F8 04 00 00 8B 86 ? ? ? ? 89 BE 64 A8 07 00 89 BE 60 A8 07 00 89 BE 5C A8 07 00 89 BE 58 A8 07 00 89 BE 54 A8 07 00 89 BE 50 A8 07 00 89 96 9C 06 00 00 89 86 ? ? ? ? 0F BE 94 31 84 C6 03 00'},
}
local M={}
local bindings
function M.resolve()
  if bindings then return bindings end
  local result={}
  for _,name in ipairs({'systemMessage','remoteImmediate','localImmediate'}) do
    local spec=contexts[name]
    local guard=require('code/hook-check').resolve(spec.pattern,'Recorder network '..name)
    local address=guard.address+spec.offset
    result[name]={address=address,bytes=core.readBytes(address,spec.size),guard=guard}
  end
  local commands=modules.protocol:getNativeCommandInterface()
  local actor=commands.localPlayer-commands.handler-4
  local remote=result.remoteImmediate.guard.address
  local localCall=result.localImmediate.guard.address
  assert(core.readInteger(remote+2)==actor and core.readInteger(localCall+68)==actor
    and core.readInteger(localCall+20)==actor+4
    and core.readInteger(remote+50)==commands.writeIndex-commands.handler+4,
    'Recorder network context disagrees with Protocol command layout')
  bindings=result
  return result
end
return M
