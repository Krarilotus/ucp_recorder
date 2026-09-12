-- Completed native subtotals, immediately before the checksum send epilogue.
local pattern='8B 86 ? ? ? ? 8D 14 40 8B 44 24 10 C1 E2 04 89 84 32 14 A9 07 00 8B 8E ? ? ? ? 01 84 8E 98 A8 07 00 39 6C 24 54 8D B4 8E 98 A8 07 00 5F 5D 5B 0F 85 ? ? ? ? 5E 83 C4 40 C7 44 24 04 0C 00 00 00 B9 ? ? ? ? E9 ? ? ? ?'
local M={}
local binding
function M.resolve()
  if binding then return binding end
  local guard=require('code/hook-check').resolve(pattern,'Recorder completed world hashes')
  local commands=modules.protocol:getNativeCommandInterface()
  local player=commands.localPlayer-commands.handler
  assert(core.readInteger(guard.address+2)==player and core.readInteger(guard.address+25)==player
    and core.readInteger(guard.address+69)==commands.handler,
    'Recorder world hashes disagree with Protocol command layout')
  local address=guard.address+36
  binding={address=address,bytes=core.readBytes(address,11),guard=guard}
  return binding
end
return M
