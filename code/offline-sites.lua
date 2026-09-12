-- Offline gates retain the native multiplayer world and command translation.
-- Resolve the existing transport/pacing boundaries through their native owners.
local M={}
local binding,guards
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local patterns=require('code/offline-patterns')
  local commands=require('code/native-command').bind({}).commands
  local state=require('code/engine-state-sites').resolve()
  local save=require('code/native-save').interface()
  local phases=require('code/maintenance-sites').resolve()
  local function integer(a) return core.readInteger(a) end
  local function relative(a) return a+5+integer(a+1) end
  local g={save=check.context(save.writeWorld+0x1a4,patterns.save,'Recorder save pacing'),
    queue=check.context(commands.queueEntry+0x11c,patterns.queue,'Recorder native transport callers'),
    receive=check.context(phases.receiveEntry,patterns.receive,'Recorder native receive loop'),
    menu=state.haltingMenu.guard}
  local s,q=g.save.address,g.queue.address
  local worker=relative(s+41)
  g.worker=check.context(worker,patterns.worker,'Recorder native synchronization worker')
  g.syncPacket=check.context(relative(worker+33),patterns.syncPacket,'Recorder synchronization packet')
  g.syncMessage=check.context(relative(worker+64),patterns.syncMessage,'Recorder synchronization message')
  g.transmit=check.context(relative(q+12),patterns.transmit,'Recorder native transmission')
  for _,name in ipairs({'pacing','autosave','syncPolling','lag'}) do
    g[name]=check.resolve(patterns[name],'Recorder offline '..name)
  end
  local offset=commands.writeIndex-commands.handler
  assert(integer(s+8)==commands.handler+0x618 and integer(s+37)==commands.handler
    and relative(q+77)==g.transmit.address and integer(q+19)==offset
    and integer(q+26)==offset and integer(q+42)==offset,
    'Recorder offline callers disagree with Map/Protocol')
  assert(integer(worker+14)==offset-16 and integer(worker+29)==offset-16
    and integer(worker+42)==offset-12 and integer(worker+60)==offset-12,
    'Recorder synchronization clock fields disagree')
  local p,a,l,n=g.pacing.address,g.autosave.address,g.lag.address,g.syncPolling.address
  assert(integer(p+5)==state.gameCore+0xc8 and integer(p+22)==state.gameCore+0xc8
    and integer(p+33)==state.gameCore+0xa4 and integer(p+84)==state.gameCore+0xa8
    and integer(p+90)==offset-0x30a8,
    'Recorder pacing state disagrees with native owners')
  assert(integer(g.receive.address+34)==offset-0x4c and integer(n+27)==offset-0x4c
    and integer(n+38)==offset-0x4c and integer(n+1)==commands.handler+0x618
    and relative(n+45)==worker,'Recorder receive/polling contexts disagree')
  assert(integer(a+41)==offset-0xc40 and integer(a+54)==offset-0xc3c
    and integer(a+66)==state.gameCore and integer(l+83)==state.gameCore
    and relative(l+46)==commands.queueEntry
    and integer(g.syncMessage.address+47)==commands.tick
    and integer(g.syncPacket.address+49)==state.gameCore
    and integer(g.syncPacket.address+74)==commands.tick
    and relative(a+70)==relative(l+87) and relative(a+70)==relative(g.syncPacket.address+53),
    'Recorder offline game-view/clock contexts disagree')
  local function site(context,offset,size,patch,value,pop)
    return {address=context.address+offset,bytes=core.readBytes(context.address+offset,size),
      guard=context,patch=patch,value=value,pop=pop}
  end
  binding={savePacing=site(g.save,7,5,'constant',99),
    pacing=site(g.pacing,55,6,'constant',99),pauseMenu=site(g.menu,0,5,'constant',99),
    receive=site(g.receive,0,8,'return'),transmit=site(g.transmit,0,6,'return',nil,20),
    syncMessage=site(g.syncMessage,0,9,'return',nil,4),
    syncPacket=site(g.syncPacket,12,6,'constant',99),autosave=site(g.autosave,0,9,'return'),
    syncPolling=site(g.syncPolling,0,5,'return'),lag=site(g.lag,0,5,'return')}
  guards=g
  return binding
end
function M.verify()
  local result=M.resolve()
  for name,guard in pairs(guards) do
    require('code/hook-check').verify(guard,'Recorder offline context changed: '..name)
  end
  return result
end
return M
