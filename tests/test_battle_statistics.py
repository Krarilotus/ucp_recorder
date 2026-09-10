"""Snapshots preserve the observed boundary and never lend mutable game state to UI."""
import unittest
import test_recorder as fixture


class BattleStatisticsTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check(r'''
function core.readString(a,n)
 local s={}; for i=0,n-1 do s[#s+1]=string.char(bytes[a+i] or 0) end; return table.concat(s)
end
function core.writeString(a,s) for i=1,#s do bytes[a+i-1]=s:byte(i) end end
function core.writeInteger(a,v)
 for i=0,3 do bytes[a+i]=math.floor(v/256^i)%256 end
end
function core.readInteger(a)
 local v=0; for i=0,3 do v=v+(bytes[a+i] or 0)*256^i end; return v
end
function core.readSmallInteger(a) return (bytes[a] or 0)+(bytes[a+1] or 0)*256 end
function core.copyMemory(a,b,n) core.writeString(a,core.readString(b,n)) end
layout={pack=1000,temporary=2000,results=8000,groups=11000,ai=11100,alive=11200}
core.writeInteger(layout.pack+0x2b,1234-layout.pack-0x2f)
core.exposeCode=function(a,count,convention)
 assert(count==1 and convention==0)
 if a==layout.pack then return function()
  core.writeString(layout.temporary,string.rep('\0',0xbf0))
  core.writeString(layout.temporary+4,'Map\0')
  if failPack then error('packer failed') end
 end end
 assert(a==1234); return function(slot) assert(slot==2); return core.readInteger(layout.results+0x334+slot*4) end
end
engine={sites={gameCore=12000},tick=function() return now end,player=function() return 2 end}
now=100
wallClock=0
require('code/platform').multimediaMilliseconds=function() return wallClock end
sha={sha256=function(s) return s end}
package.loaded['code/sessions']={path=function(id) return id end,write=function(p,s) files[p]=s end}
package.loaded['code/world-reader']={read=function(p,n) return files[p] end}
stats=require('code/battle-statistics'); battle=stats.new(engine,layout)
core.writeString(layout.temporary,string.rep('X',stats.SIZE))
''')

    def test_named_boundary_stays_frozen_while_recording_continues(self):
        self.check(r'''
core.writeInteger(layout.results+0x33c,40); bytes[layout.alive+4]=1
battle:begin()
assert(core.readString(layout.temporary,stats.SIZE)==string.rep('X',stats.SIZE))
local saved={id='snapshot',lastTick=100}; battle:write(saved)
local raw=stats.read(saved)
now=200; core.writeInteger(layout.results+0x33c,99); bytes[layout.alive+4]=0
battle:observe(); local full={id='full',lastTick=200}; battle:write(full)
assert(stats.read(saved)==raw and stats.read(full)~=raw)
assert(raw:byte(0x478+0x33c+1)==40 and raw:byte(0x43c+8+1)==1)
assert(core.readString(layout.temporary,stats.SIZE)==string.rep('X',stats.SIZE))
assert(not pcall(battle.write,battle,{id='wrong',lastTick=199}))
saved.lastTick=99; assert(not pcall(stats.read,saved))
''')

    def test_native_temporary_is_restored_even_when_packer_fails(self):
        self.check('''
failPack=true; assert(not pcall(battle.begin,battle))
assert(core.readString(layout.temporary,stats.SIZE)==string.rep('X',stats.SIZE))
''')

    def test_elapsed_time_does_not_require_a_native_save_and_handles_clock_wrap(self):
        self.check('''
core.writeInteger(engine.sites.gameCore+0x236c,4294907296)
core.writeInteger(engine.sites.gameCore+0x2370,0) -- never refreshed by a save
battle:begin(); wallClock=120000
local saved={id='elapsed',lastTick=100}; battle:write(saved)
assert(core.readInteger(battle.buffer+0x470)==3)
assert(core.readInteger(engine.sites.gameCore+0x2370)==0)
assert(core.readInteger(engine.sites.gameCore+0x236c)==4294907296)
local raw=stats.read(saved)
wallClock=180000; now=200; battle:observe(); battle:write({id='later',lastTick=200})
assert(core.readInteger(battle.buffer+0x470)==4 and stats.read(saved)==raw)
''')

    def test_history_dates_and_names_do_not_change_snapshot_results(self):
        self.check(r'''
realNative.profile.name='SHC'
battle:begin(); local a={id='a',lastTick=100,variant='SHC',created='2026-09-09T10:00:00Z'}
battle:write(a)
now=200; battle:observe()
local b={id='b',lastTick=200,variant='SHC',created='2026-09-09T11:00:00Z',status='failed'}
battle:write(b)
a.savedAt='2026-09-09T10:00:00Z'; b.savedAt='2026-09-09T11:00:00Z'
-- The later saved entry must win even if its recording started earlier.
b.created='2026-09-09T09:00:00Z'
local store=require('code/sessions'); store.ROOT='replays'; store.list=function() return {a,b} end
store.read=function() error('no aliases') end
store.save=function(m) assert(m==b) end
local history=require('code/battle-history').new({storedCount=15000})
history:refresh(); assert(#history.items==2 and history.items[1].id=='b')
history.selected=history.items[1]; history:rename('Checkpoint')
local raw=history:display(history.selected)
assert(raw:sub(5,14)=='Checkpoint' and #raw==stats.SIZE)
assert(raw:sub(1005)==stats.read(b):sub(1005))
assert(history.selected.id=='b' and b.status=='failed' and b.lastTick==200)
history:sort(4); assert(history.items[1].id=='a' and not history.descending)
history:sort(4); assert(history.items[1].id=='b' and history.descending)
history.selected={id='native',raw=raw}; assert(not pcall(history.rename,history,'Leave alone'))
''')

    def test_only_an_explicit_native_result_link_merges_one_history_entry(self):
        self.check(r'''
realNative.profile.name='SHC'
battle:begin(); local replay={id='replay',lastTick=100,variant='SHC',created='2026-09-10T01:00:00Z'}
battle:write(replay)
local raw=stats.read(replay)
local sites={records=20000,storedCount=19000}
core.writeInteger(sites.storedCount,2)
core.writeString(sites.records,raw); core.writeString(sites.records+stats.SIZE,raw)
require('code/sessions').list=function() return {replay} end
local history=require('code/battle-history').new(sites)
history:refresh(); assert(#history.items==3) -- same fields are not an identity proof
replay.nativeBattleHash=sha.sha256(raw)
history:refresh(); assert(#history.items==2)
assert(history.items[1].manifest==replay and not history.items[2].manifest)
assert(core.readInteger(sites.storedCount)==2)
assert(core.readString(sites.records,2*stats.SIZE)==raw..raw)
require('code/sessions').list=function() return {} end
history:refresh(); assert(#history.items==2) -- removing a replay reveals the native result again
''')
