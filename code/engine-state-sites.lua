-- Existing replay clock/pause/calendar bindings. Execute the original native
-- coordinator and countdown logic; never replace them with a Lua update loop.
local patterns={
  entry='83 3D ? ? ? ? 00 56 8B F1 C7 05 ? ? ? ? 00 00 00 00 74 14 83 3D ? ? ? ? 00 74 79 B9 ? ? ? ? 5E E9 ? ? ? ?',
  exit='83 F8 0A 75 18 6A 64 B9 ? ? ? ? C7 05 ? ? ? ? 0B 00 00 00 E8 ? ? ? ? 5E C3',
  clock='B9 ? ? ? ? E8 ? ? ? ? 85 C0 74 45 83 3D ? ? ? ? 00 74 09 83 3D ? ? ? ? 08 7D 46 B9 ? ? ? ? E8 ? ? ? ? 85 C0 75 25 B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 83 05 ? ? ? ? 01 B9 ? ? ? ? E8 ? ? ? ?',
  pause='83 3D ? ? ? ? 00 75 2D A1 ? ? ? ? 85 C0 0F 8F ? ? ? ? 75 14 B9 ? ? ? ? E8 ? ? ? ? 85 C0 0F 85 ? ? ? ? EB 0A C7 05 ? ? ? ? 00 00 00 00',
  menu='A1 ? ? ? ? 85 C0 74 08 83 F8 63 74 03 33 C0 C3 83 3D ? ? ? ? 00 74 06 B8 01 00 00 00 C3 33 C0 83 3D ? ? ? ? 1C 0F 94 C0 C3',
  navigation='55 8B EC 83 EC 40 53 56 8B F1 33 C9 39 4D 08 89 75 E0 8D 59 01 74 07 89 5E 6C 33 C0 EB 05 A1 ? ? ? ? 2B C3 3B C1 A3 ? ? ? ? 7E 0A 5E 33 C0 5B 8B E5 5D C2 04 00 C7 05 ? ? ? ? ? ? ? ? 39 4E 6C',
  calendar='8B 54 24 08 33 C0 89 81 ? ? ? ? 89 81 ? ? ? ? 89 81 ? ? ? ? 89 81 ? ? ? ? 8B 44 24 04 89 81 ? ? ? ? B8 64 00 00 00 89 91 ? ? ? ?',
}
local M={}
local binding,guards,controls
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local phases=require('code/maintenance-sites').resolve()
  local caller=phases.guards[1]
  local tick=caller.address+20+core.readInteger(caller.address+16)
  local commands=require('code/native-command').bind({}).commands
  local rng=require('code/rng-bindings').resolve()
  local g={caller=caller}
  g.entry=check.context(tick,patterns.entry,'Recorder coordinator entry')
  g.exit=check.context(tick+0x7d,patterns.exit,'Recorder coordinator return')
  g.clock=check.context(tick+0x106,patterns.clock,'Recorder clock admission')
  g.pause=check.context(tick+0x1e8,patterns.pause,'Recorder world pause admission')
  local function relative(a) return a+5+core.readInteger(a+1) end
  local c=g.clock.address
  local gameCore=core.readInteger(c+1)
  local paused=core.readInteger(c+16)
  local menu=relative(c+37)
  g.menu=check.context(menu,patterns.menu,'Recorder native halting-menu query')
  assert(gameCore==commands.tick-0x98 and paused==gameCore+0x2344
    and core.readInteger(c+33)==gameCore and core.readInteger(c+68)==commands.tick
    and core.readInteger(c+47)==rng.state and core.readInteger(c+57)==rng.state
    and relative(c+51)==rng.streams[2].address and relative(c+61)==rng.streams[1].address
    and core.readInteger(c+74)==phases.gameState,
    'Recorder clock context disagrees with native owners')
  assert(core.readInteger(tick+2)==commands.handler+0xcbc
    and core.readInteger(tick+24)==commands.handler+0x790
    and core.readInteger(tick+32)==commands.handler
    and core.readInteger(g.exit.address+8)==commands.handler
    and core.readInteger(g.exit.address+14)==commands.handler+0xb98
    and relative(g.exit.address+22)==commands.queueEntry,
    'Recorder coordinator command context disagrees with Protocol')
  local p=g.pause.address
  assert(core.readInteger(p+2)==core.readInteger(tick+12)
    and core.readInteger(p+10)==paused and core.readInteger(p+25)==gameCore
    and relative(p+29)==menu and core.readInteger(p+46)==paused
    and p+22+core.readInteger(p+18)==g.exit.address+27
    and p+42+core.readInteger(p+38)==g.exit.address+27
    and core.readInteger(menu+1)==commands.handler+0x618,
    'Recorder native pause contexts disagree')
  local menuText=core.readInteger(menu+19)-0x5c
  require('code/validation').integer(menuText,0x10000,0x7fffffff-0x1000,'Native menu input state')
  -- This call already belongs to the verified maintenance phase. Legacy may
  -- change the reset period from 200 to 50; the countdown stays native.
  local navigation=relative(phases.maintenance.address+47)
  g.navigation=check.context(navigation,patterns.navigation,'Recorder native navigation countdown')
  local countdown=core.readInteger(navigation+31)
  require('code/validation').integer(countdown,0x10000,0x7fffffff-4,'Native navigation countdown')
  assert(core.readInteger(navigation+40)==countdown and core.readInteger(navigation+58)==countdown,
    'Recorder navigation countdown operands disagree')
  g.calendar=check.resolve(patterns.calendar,'Recorder native calendar setter')
  local a=g.calendar.address
  local month=core.readInteger(a+36)
  require('code/validation').integer(month,0,0x200000,'Native calendar offset')
  assert(core.readInteger(a+47)==month+4 and core.readInteger(a+26)==month-4
    and core.readInteger(a+8)==month+24 and core.readInteger(a+14)==month+16
    and core.readInteger(a+20)==month+20,'Recorder calendar field layout differs')
  local function site(guard,offset,size)
    return {address=guard.address+offset,bytes=core.readBytes(guard.address+offset,size),guard=guard}
  end
  binding={tickEntry=site(g.entry,0,7),tickExit=site(g.exit,27,2),tick=site(g.clock,46,5),
    tickReturned=site(caller,20,5),haltingMenu=site(g.menu,0,45),
    calendar=site(g.calendar,30,21),gameCore=gameCore,paused=paused,
    navigationCountdown=countdown,menuText=menuText}
  binding.tickEntry.kind='raw';binding.tickEntry.patch='return'
  binding.calendar.value=phases.gameState+month
  controls={pause=site(g.pause,7,7),pausedCamera=site(g.clock,23,7)}
  controls.pause.kind='branch';controls.pause.patch='fallthrough'
  controls.pause.target=g.pause.address+54;controls.pause.condition=133
  controls.pausedCamera.kind='raw';controls.pausedCamera.patch='equalFlags'
  guards=g
  return binding
end
function M.controls()
  M.resolve()
  return controls
end
function M.bind(sites)
  local result={}
  for key,value in pairs(sites) do result[key]=value end
  for key,value in pairs(M.resolve()) do result[key]=value end
  return result
end
function M.verify()
  M.resolve()
  for key,guard in pairs(guards) do
    require('code/hook-check').verify(guard,'Recorder state context changed: '..key)
  end
end
return M
