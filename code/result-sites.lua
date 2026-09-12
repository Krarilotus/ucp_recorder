-- Recorder observes the existing result insertion and calls the native packer
-- and scorer. UI retains menu transitions; Protocol supplies the local player.
local M={}
local binding,guards
function M.resolve()
  if binding then return binding end
  local check=require('code/hook-check')
  local patterns=require('code/result-patterns')
  local state=require('code/engine-state-sites').resolve()
  local commands=require('code/native-command').bind({}).commands
  local menu=require('code/load-sites').resolve().menuTransition
  local g={timer=check.resolve(patterns.timer,'Recorder native results timer'),
    resources=check.resolve(patterns.resources,'Recorder native resource recount'),
    store=check.resolve(patterns.store,'Recorder native result insertion')}
  local function integer(a) return core.readInteger(a) end
  local function relative(a) return a+5+integer(a+1) end
  local function pointer(a,size,label)
    return require('code/validation').integer(a,0x10000,0x7fffffff-size,label)
  end
  local t,r,s=g.timer.address,g.resources.address,g.store.address
  local alive=integer(t+42)
  pointer(alive,18,'Native alive array')
  assert(integer(t+34)==commands.localPlayer and integer(t+50)==state.gameCore
    and integer(t+58)==state.gameCore+0x2376 and relative(t+69)==menu.guard.address,
    'Recorder results timer disagrees with Protocol/UI')
  local resources=integer(r+55)
  pointer(resources,9*0x39f4,'Native player resources')
  assert(integer(r+21)==resources+15*4,'Recorder resource recount layout differs')
  local pack=relative(s+5)
  g.pack=check.context(pack,patterns.pack,'Recorder native battle statistics packer')
  local temporary=integer(pack+5)
  local results=integer(pack+0x18e)
  local groups=integer(pack+0x56)-4
  local ai=integer(pack+0xab)-4
  local score=relative(pack+0x2a)
  g.score=check.context(score,patterns.score,'Recorder native battle score')
  pointer(temporary,0xbf0,'Native temporary battle entry')
  pointer(results,0x778,'Native accumulated battle statistics')
  pointer(groups,36,'Native battle groups');pointer(ai,36,'Native battle AI slots')
  assert(integer(pack+24)==temporary+4 and integer(pack+37)==commands.localPlayer
    and integer(pack+0x33)==temporary+0x3ec and integer(pack+0x42)==results+0x32a
    and integer(pack+0x61)==temporary+0x3f0
    and integer(pack+0x16c)==state.gameCore+0x2314
    and integer(pack+0x17f)==temporary+0x460
    and integer(pack+0x193)==temporary+0x478,
    'Recorder battle entry layout disagrees with native owners')
  -- Check every unrolled player read/write, including the word-to-int alive
  -- conversion. These are field offsets in the verified complete packer body.
  local groupReads={0x56,0x5b,0x67,0x73,0x7d,0x89,0x95,0x9f}
  local groupWrites={0x6d,0x78,0x83,0x8f,0x9a,0xa5,0xb1,0xbc}
  local aiReads={0xab,0xb7,0xc1,0xcd,0xd9,0xe3,0xef,0xfb}
  local aiWrites={0xc7,0xd3,0xde,0xe9,0xf5,0x100,0x10d,0x11a}
  local aliveReads={0x107,0x114,0x121,0x12d,0x13a,0x147,0x153,0x160}
  local aliveWrites={0x126,0x133,0x140,0x14c,0x159,0x166,0x173,0x179}
  for i=1,8 do
    assert(integer(pack+groupReads[i])==groups+4*i
      and integer(pack+groupWrites[i])==temporary+0x3f4+4*i
      and integer(pack+aiReads[i])==ai+4*i
      and integer(pack+aiWrites[i])==temporary+0x418+4*i
      and integer(pack+aliveReads[i])==alive+2*i
      and integer(pack+aliveWrites[i])==temporary+0x43c+4*i,
      'Recorder battle player layout differs at slot '..i)
  end
  for offset,field in pairs({[8]=0x334,[22]=0x5bd,[30]=0x634,[52]=0x610,
    [71]=0x714,[77]=0x70c,[90]=0x710,[96]=0x718}) do
    assert(integer(score+offset)==results+field,'Recorder native score statistics differ')
  end
  local records=integer(s+0x9d)
  local storedCount=integer(s+22)
  pointer(records,250*0xbf0,'Native battle history')
  assert(storedCount==records-4 and integer(s+0xaf)==storedCount
    and integer(s+0xbc)==storedCount and integer(s+0x6c)==records
    and integer(s+0x3f)==records+0x3ec and integer(s+0x3a)==temporary+0x3ec
    and integer(s+0xa7)==temporary and s+21+integer(s+17)==s+202,
    'Recorder battle insertion layout differs')
  local function site(context,offset,size)
    return {address=context.address+offset,bytes=core.readBytes(context.address+offset,size),guard=context}
  end
  local timer=site(g.timer,26,5);timer.kind='raw';timer.patch='equalFlags'
  local insertion=site(g.store,0xad,10);insertion.records=records
  binding={engine={resultsTimer=timer,resultsBranch=site(g.timer,31,2),
      playerResources=resources,resourceReset=site(g.resources,52,13)},
    statistics={pack=pack,score=score,temporary=temporary,results=results,groups=groups,ai=ai,alive=alive},
    insertion=insertion,records=records,storedCount=storedCount}
  guards=g
  return binding
end
function M.bind(sites)
  local result={}
  for key,value in pairs(sites) do result[key]=value end
  for key,value in pairs(M.resolve().engine) do result[key]=value end
  return result
end
function M.verify()
  local result=M.resolve()
  for name,guard in pairs(guards) do
    require('code/hook-check').verify(guard,'Recorder results context changed: '..name)
  end
  return result
end
return M
