-- Protocol owns queue/scheduler entries. Recorder retains its existing replay
-- guards around native payload copying, selection and completed dispatch.
local patterns={
  copy='8B 8E 24 D8 02 00 8B 54 24 20 69 C9 F8 04 00 00 39 AC 31 7C C6 03 00 8D 04 31 7E 3B 05 86 C6 03 00 50 8B 86 30 D8 02 00 52 50 B9 ? ? ? ? E8 ? ? ? ? 01 9E ? ? ? ? 81 BE ? ? ? ? C8 00 00 00',
  localTimed='8D 0C 30 89 BE ? ? ? ? 8B 81 7C C6 03 00 3B C7 7E 41 8B 96 2C D8 02 00 52 8B 96 30 D8 02 00 52 81 C1 86 C6 03 00 51 50 53 8B CE',
  dispatcher='56 8B F1 E8 ? ? ? ? 85 C0 0F 84 B9 00 00 00 55 57 33 FF 33 ED 39 BE ? ? ? ? 0F 8E A5 00 00 00 53 8D 9E ? ? ? ? 8D A4 24 00 00 00 00 8B 03 89 86 24 D8 02 00 69 C0 F8 04 00 00 8B 84 30 80 C6 03 00 50 8B CE E8 ? ? ? ? 8B 8E 24 D8 02 00 69 C9 F8 04 00 00 89 86 ? ? ? ? 89 BE 64 A8 07 00 89 BE 60 A8 07 00 89 BE 5C A8 07 00 89 BE 58 A8 07 00 89 BE 54 A8 07 00 89 BE 50 A8 07 00 89 BE 28 D8 02 00 89 BE ? ? ? ? 0F BE 94 31 84 C6 03 00',
  executed='8B 8E 24 D8 02 00 69 C9 F8 04 00 00 83 C5 01 C6 84 31 85 C6 03 00 0A 83 C3 08',
  selector='51 53 56 8B F1 57 8D 86 ? ? ? ? 50 6A 00 68 20 03 00 00 B9 ? ? ? ? C7 86 ? ? ? ? 00 00 00 00 E8 ? ? ? ? 8B BE ? ? ? ? 81 FF C8 00 00 00 7D 76 8B CF 69 C9 F8 04 00 00 8D 9C 31 85 C6 03 00 8A 03 84 C0 74 50 3C 0A 7D 4C 8B 53 F7 3B 15 ? ? ? ? 7F 41',
}
local M={}
local bindings
function M.resolve()
  if bindings then return bindings end
  local commands=require('code/native-command').bind({}).commands
  for _,key in ipairs({'queueEntry','scheduleEntry'}) do
    require('code/validation').integer(commands[key],0x10000,0x7fffffff-0x300,'Protocol '..key)
  end
  local check=require('code/hook-check')
  assert(type(commands.queueBytes)=='string' and #commands.queueBytes==69
    and type(commands.scheduleBytes)=='string' and #commands.scheduleBytes==79,
    'Recorder requires Protocol 1.1.4 native entry guards')
  local queue={address=commands.queueEntry,bytes={commands.queueBytes:byte(1,#commands.queueBytes)}}
  local schedule={address=commands.scheduleEntry,bytes={commands.scheduleBytes:byte(1,#commands.scheduleBytes)}}
  check.verify(queue,'Recorder native queue entry changed')
  check.verify(schedule,'Recorder native scheduler entry changed')
  local copy=check.context(commands.scheduleEntry+0x143,patterns.copy,'Recorder received payload copy')
  local timed=check.context(commands.queueEntry+0xfc,patterns.localTimed,'Recorder local timed payload')
  local address=require('code/maintenance-sites').resolve().commandDispatcher
  require('code/validation').integer(address,0x10000,0x7fffffff-0x100,'Native command dispatcher')
  local dispatch=check.context(address,patterns.dispatcher,'Recorder native command dispatch')
  local executed=check.context(address+0xa0,patterns.executed,'Recorder completed command dispatch')
  local selector=check.context(address+8+core.readInteger(address+4),patterns.selector,'Recorder native command selection')
  local selected=core.readInteger(selector.address+8)
  local count=core.readInteger(selector.address+27)
  local actor=commands.localPlayer-commands.handler-4
  require('code/validation').integer(selected,0,0x200000,'Native selected command offset')
  assert(count==selected+800 and core.readInteger(address+24)==count
    and core.readInteger(address+37)==selected and core.readInteger(address+91)==actor
    and core.readInteger(selector.address+84)==commands.tick,
    'Recorder selected-command layout disagrees with Protocol')
  local write=commands.writeIndex-commands.handler
  assert(core.readInteger(queue.address+6)==write and core.readInteger(timed.address+5)==write+4
    and core.readInteger(address+139)==write+4 and core.readInteger(selector.address+42)==write-4,
    'Recorder command-index operands disagree with Protocol')
  local function site(guard,offset,size)
    return {address=guard.address+offset,bytes=core.readBytes(guard.address+offset,size),guard=guard}
  end
  bindings={queue=site(queue,0,10),select=site(selector,0,5),copySize=site(copy,34,6),
    localTimed=site(timed,26,6),commandBoundary=site(dispatch,48,8),
    execute=site(dispatch,143,8),executed=site(executed,0,6),
    selectedOffset=selected,selectedCountOffset=count,actorOffset=actor}
  bindings.copySize.ownerGuard=schedule
  return bindings
end
function M.bind(sites)
  local result={}
  for key,value in pairs(sites) do result[key]=value end
  for key,value in pairs(M.resolve()) do result[key]=value end
  return result
end
function M.verify()
  for key,site in pairs(M.resolve()) do
    if type(site)=='table' then
      require('code/hook-check').verify(site.guard,'Recorder command hook conflicts at '..key)
      if site.ownerGuard then require('code/hook-check').verify(site.ownerGuard,'Protocol native entry changed') end
    end
  end
end
return M
