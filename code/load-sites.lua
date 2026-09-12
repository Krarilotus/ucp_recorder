-- Reuse RNG initialization, UI transition and Map's wrapped reader. Recorder
-- keeps the existing distinction between failed loads and completed worlds.
local patterns={
  prepare='57 89 3D ? ? ? ? E8 ? ? ? ? 83 C4 04 5E 5D 5B C7 05 ? ? ? ? 01 00 00 00 5F C3',
  load='81 EC F4 03 00 00 A1 ? ? ? ? 33 C4 89 84 24 F0 03 00 00 A1 ? ? ? ? 53 33 DB 3B C3 74 11 83 F8 63 74 0C 39 1D ? ? ? ? 0F 85 FE 06 00 00 A1 ? ? ? ? 83 E8 1F 55 0F 84 47 02 00 00',
  begin='8B 0D ? ? ? ? 8B 15 ? ? ? ? 56 57 53 8D 34 0A 83 CF FF 57 B9 ? ? ? ? 89 1D ? ? ? ? E8 ? ? ? ? A1 ? ? ? ? 83 F8 2F 75 59 8B 04 B5 ? ? ? ? 50',
  done='B9 ? ? ? ? E8 ? ? ? ? 5D 8B 8C 24 F4 03 00 00 5B 33 CC E8 ? ? ? ? 81 C4 F4 03 00 00 C3',
  reset='83 F8 2F 0F 85 FF 01 00 00 33 DB 53 6A 1D B9 ? ? ? ? E8 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 5F 5E 89 1D ? ? ? ? B9 ? ? ? ? 5B E9 ? ? ? ? B9 ? ? ? ? E8 ? ? ? ? 33 DB 53 6A FF B9 ? ? ? ? 89 1D ? ? ? ? E8 ? ? ? ? 53 6A FF B9 ? ? ? ? E8 ? ? ? ? 53',
  readFile='55 57 B9 ? ? ? ? E8 ? ? ? ? 53 68 00 80 00 00 50 E8 ? ? ? ? 8B F8 83 CD FF 83 C4 0C 3B FD',
  fileName='8B 81 C4 0B 00 00 69 C0 E9 03 00 00 8D 84 08 E0 AE 07 00 C3',
  mapName='8B 44 24 04 3D F4 01 00 00 7C 05 33 C0 C2 04 00 69 C0 E9 03 00 00 8D 84 08 C8 0B 00 00 C2 04 00',
  readComplete='FF 15 ? ? ? ? 2B 05 ? ? ? ? 5F A3 ? ? ? ? 89 1D ? ? ? ? 5D 5E 5B 83 C4 0C C2 04 00',
}
local M={}
local binding,guards
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local state=require('code/engine-state-sites').resolve()
  local rng=require('code/rng-bindings').resolve()
  local commands=require('code/native-command').bind({}).commands
  local save=require('code/native-save').interface()
  local ui=modules and modules.ui
  assert(ui and type(ui.getNativeMenuInterface)=='function','Recorder requires UI 1.0.2 native menu interface')
  local menu=ui:getNativeMenuInterface()
  assert(menu and menu.version==1 and menu.gameCore==state.gameCore
    and type(menu.bytes)=='string' and #menu.bytes==60,'Recorder native UI interface differs')
  require('code/validation').integer(menu.entry,0x10000,0x7fffffff-60,'UI native transition entry')
  local g={menu={address=menu.entry,bytes={menu.bytes:byte(1,#menu.bytes)}},initialization=rng.initialization}
  check.verify(g.menu,'UI native transition changed')
  check.verify(g.initialization,'Native match initialization changed')
  g.prepare=check.context(g.initialization.address+61,patterns.prepare,'Recorder match preparation')
  assert(core.readInteger(g.prepare.address+20)==state.gameCore+0x2384,
    'Recorder match preparation has a different GameCore')
  local function relative(a) return a+5+core.readInteger(a+1) end
  g.load=check.resolve(patterns.load,'Recorder outer load handler')
  local a=g.load.address
  assert(core.readInteger(a+21)==commands.handler+0x618
    and core.readInteger(a+39)==commands.handler+0xcbc
    and core.readInteger(a+50)==state.menuText+0x58,'Recorder load handler state disagrees with owners')
  g.begin=check.context(a+64+core.readInteger(a+60),patterns.begin,'Recorder load beginning')
  g.done=check.context(a+49+core.readInteger(a+45)-11,patterns.done,'Recorder load completion')
  local b=g.begin.address
  assert(core.readInteger(b+2)==state.menuText+0x7c and core.readInteger(b+8)==state.menuText+0x80
    and core.readInteger(b+39)==state.gameCore+0xc,'Recorder load selection state differs')
  g.reset=check.resolve(patterns.reset,'Recorder world reset')
  assert(core.readInteger(g.reset.address+54)==core.readInteger(g.done.address+1)
    and relative(g.reset.address+58)==relative(g.done.address+5)
    and core.readInteger(g.reset.address+15)==state.gameCore
    and core.readInteger(g.reset.address+25)==state.menuText
    and relative(g.reset.address+19)==menu.entry,
    'Recorder load/reset finalization owners disagree')
  g.readFile=check.context(save.readWorld+0x44,patterns.readFile,'Map native filename call')
  local resources=core.readInteger(g.readFile.address+3)
  require('code/validation').integer(resources,0x10000,0x7fffffff-0x7c000,'Native resource manager')
  g.fileName=check.context(relative(g.readFile.address+7),patterns.fileName,'Recorder resource filename')
  g.mapName=check.resolve(patterns.mapName,'Recorder map filename')
  g.readComplete=check.resolve(patterns.readComplete,'Recorder completed world read')
  local r=g.readComplete.address
  assert(r>save.readWorld and r<save.readWorld+0x1000
    and core.readInteger(r+8)==state.gameCore+0x2370
    and core.readInteger(r+14)==state.gameCore+0x236c,
    'Recorder world completion disagrees with Map/GameCore')
  local function site(guard,offset,size)
    return {address=guard.address+offset,bytes=core.readBytes(guard.address+offset,size),guard=guard}
  end
  binding={beginMatch=site(g.initialization,0,5),prepareMatch=site(g.prepare,18,10),
    menuTransition=site(g.menu,24,6),load=site(g.load,0,6),loadBegin=site(g.begin,0,6),
    loadHandlerComplete=site(g.done,0,5),resetMatch=site(g.reset,53,5),
    fileName=site(g.fileName,0,6),mapName=site(g.mapName,0,9),
    loadWorldComplete=site(g.readComplete,18,6),resources=resources}
  guards=g
  return binding
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
    require('code/hook-check').verify(guard,'Recorder load context changed: '..key)
  end
end
return M
