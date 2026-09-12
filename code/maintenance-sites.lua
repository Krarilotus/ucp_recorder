-- Existing native coordinator phases; do not replace them with a timer/tick loop.
local patterns={
  maintenance='B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 6A 00 B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ?',
  world='B9 ? ? ? ? E8 ? ? ? ? 85 C0 0F 84 52 FE FF FF 8B CE E8 ? ? ? ? 8B CE E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? C7 05 ? ? ? ? 00 00 00 00 E8 ? ? ? ?',
  caller='B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? E8 ? ? ? ? 39 1D ? ? ? ? 75 14 A1 ? ? ? ? 03 C5',
}
local worldPattern='53 55 56 33 F6 57 89 B1 ? ? ? ? 89 B1 ? ? ? ? 89 B1 ? ? ? ? 89 B1 ? ? ? ? 89 B1 ? ? ? ? 89 B1 ? ? ? ? 8D 91 ? ? ? ? 8D 6E 08 8D 5E 01 8B 02 3B C6 7E 05 83 C0 FF 89 02'
local M={}
local binding
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local guards={caller=check.resolve(patterns.caller,'Recorder phase caller')}
  local commands=modules.protocol:getNativeCommandInterface()
  local caller=guards.caller.address
  assert(core.readInteger(caller+1)==commands.handler and core.readInteger(caller+21)==commands.handler,
    'Recorder coordinator caller disagrees with Protocol')
  local gameState=core.readInteger(caller+11)
  require('code/validation').integer(gameState,0x10000,0x7fffffff,'Native game-state pointer')
  local tick=caller+20+core.readInteger(caller+16)
  require('code/validation').integer(tick,0x10000,0x7fffffff-0x300,'Native coordinator entry')
  -- Verified instruction offsets within this coordinator, checked against full
  -- phase context below. These are not executable-base or fixed-RVA bindings.
  guards.maintenance=check.context(tick+0x16c,patterns.maintenance,'Recorder maintenance phase')
  guards.world=check.context(tick+0x234,patterns.world,'Recorder world phase')
  local tile=core.readInteger(guards.maintenance.address+1)
  require('code/validation').integer(tile,0x10000,0x7fffffff,'Native tile-map pointer')
  for _,offset in ipairs({11,21,53,63}) do
    assert(core.readInteger(guards.maintenance.address+offset)==tile,'Recorder maintenance tile-map operands disagree')
  end
  local address=guards.world.address+18
  local target=address+7+core.readInteger(address+3)
  require('code/validation').integer(target,0x10000,0x7fffffff-65,'Native world-update entry')
  local targetGuard=check.context(target,worldPattern,'Recorder native world update')
  binding={gameState=gameState,commandDispatcher=caller+10+core.readInteger(caller+6),
    maintenance={address=guards.maintenance.address,bytes=core.readBytes(guards.maintenance.address,5),guard=guards.maintenance},
    world={address=address,bytes=core.readBytes(address,7),target=target,guard=guards.world},
    guards={guards.caller,targetGuard}}
  return binding
end
return M
