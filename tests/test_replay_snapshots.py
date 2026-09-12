import unittest
import test_recorder as fixture


class ReplaySnapshotsTests(unittest.TestCase):
    check=fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
month,tick=12000,100
removed={}; captured=0; prepared=0
package.loaded['code/snapshot-store']={MAX_POINTS=512,MAX_WORLD=100,
 cachePath=function() return 'cache-'..captured end,
 remove=function(path) removed[#removed+1]=path; return true end,
 path=function(_,point) return 'embedded-'..point.tick end,
 validate=function(p) return p end,
 capture=function(r,path,date)
  captured=captured+1
  return {tick=tick,month=date,bytes=100,commands=0}
 end,
 prepare=function(_,point,path) prepared=prepared+1; return {point=point,path=path} end}
require('code/platform').mkdir=function() end
local completion
package.loaded['code/snapshot-jobs']={start=function(engine,path,date,commands,bookmark,done)
 local point,reason=require('code/snapshot-store').capture(engine,path,date)
 if not point then return nil,reason end
 completion=function() done(point) end
 return {cancel=function() completion=nil end}
end}
function finishSnapshots() local done=completion; completion=nil; if done then done() end end
package.loaded['code/replay-preparation']={checkStartingState=function() end}
local engine={calendarMonth=function() return month end,tick=function() return tick end,
 commandsPending=function() return pending or false end,
 isPaused=function() return paused or false end,
 pause=function() paused=true end,setPaused=function(_,v) paused=v end}
r={bookmark=function() return {} end,mode='play',active=true,status='playing',halt=5000,engine=engine,
 manifest={id='test',startTick=100,lastTick=1000,snapshotOriginMonth=12000}}
ready={manifest=r.manifest}
r.input=require('code/input-state').new(r)
Snapshots=require('code/replay-snapshots')
s=Snapshots.new(r,ready); r.snapshots=s
''')

    def test_yearly_cache_and_25_year_recording_have_separate_ownership(self):
        self.check('''
s:observe(); finishSnapshots(); assert(captured==0)
month=12012; tick=200; s:observe(); finishSnapshots(); s:observe(); finishSnapshots()
assert(captured==1 and #s.entries==1 and not r.manifest.snapshots)
r.mode='record'; r.status='recording'; local embedded=Snapshots.new(r)
month=12299; embedded:observe(); finishSnapshots(); assert(captured==1)
month=12300; tick=900; embedded:observe(); finishSnapshots()
assert(captured==2 and #r.manifest.snapshots==1 and #embedded.entries==0)
embedded:close(); assert(#removed==0)
s:close(); assert(#removed==1 and r.manifest.snapshots[1].tick==900)
''')

    def test_nearest_point_combines_embedded_and_bounded_local_cache(self):
        self.check('''
Snapshots.MAX_CACHE_BYTES=2*(100+0x9c50)
for i=1,3 do month=12000+12*i; tick=100+i*100; s:observe(); finishSnapshots() end
assert(#s.entries==2 and #removed==1)
r.manifest.snapshots={{tick=150},{tick=900}}
assert(s:nearest(140)==nil and s:nearest(200).point.tick==150)
assert(s:nearest(350).point.tick==300 and s:nearest(950).point.tick==900)
month=12012; s:observe(); finishSnapshots(); assert(captured==3)
''')

    def test_restore_after_finished_preserves_cache_and_stops_before_pending_tick(self):
        self.check('''
month=12012; tick=550; s:observe(); finishSnapshots(); r.status='finished'; paused=true
local original=r.manifest
r.reset=function(self) assert(not self.snapshots); self.mode='none' end
r.startPlayback=function(self,id,_,actual,cached)
 assert(id=='test' and actual==ready and cached.point.tick==550)
 self.mode='play'; self.status='playing'; self.manifest=original
 self.snapshots=Snapshots.new(self,actual)
end
s:request(0.5); assert(s.requested==550)
s:advance(); assert(r.snapshots==s and #s.entries==1 and #removed==0 and not paused)
assert(s:atBoundary(550) and paused and memory[r.halt]==1)
assert(s:afterTick() and memory[r.halt]==0)
assert(not s:afterTick() and not s:atBoundary(550))
''')

    def test_cache_failure_falls_back_to_normal_start_without_silently_loading_bad_data(self):
        self.check('''
month=12012; tick=400; s:observe(); finishSnapshots(); tick=800
require('code/snapshot-store').prepare=function() error('damaged cache') end
r.reset=function(self) self.mode='none' end
r.startPlayback=function(self,id,_,actual,cached)
 assert(not cached and actual==ready); self.mode='play'; self.status='playing'
end
s:request(0.5); s:advance(); assert(s.target==550)
assert(not s:atBoundary(549)); assert(not s:atBoundary(550)) -- Preserve playing state.
assert(not s.target and not paused)
''')

    def test_capture_waits_for_empty_command_ring_and_disables_only_cache_on_io_failure(self):
        self.check('''
month=12012; pending=true; s:observe(); finishSnapshots(); assert(captured==0)
pending=false; require('code/snapshot-store').capture=function() return nil,'disk full' end
s:observe(); finishSnapshots(); assert(s.disabled and r.status=='playing' and #s.entries==0)
''')

    def test_damaged_starting_save_does_not_drop_running_world(self):
        self.check('''
require('code/replay-preparation').checkStartingState=function() error('damaged start') end
tick=800
r.reset=function() error('Must retain active world') end
s:request(0.1); s:advance()
assert(r.snapshots==s and r.status=='playing' and s.error:find('damaged start',1,true))
assert(not s.target and not s.requested)
''')

    def test_forward_seek_reuses_current_world_when_it_is_the_nearest_start(self):
        self.check('''
tick=400; paused=true
r.reset=function() error('Forward seek must not reload the current world') end
require('code/replay-preparation').checkStartingState=function() error('No disk read is needed') end
s:request(.5); s:advance()
assert(s.target==550 and not paused and not s.error)
assert(not s:atBoundary(549) and s:atBoundary(550) and paused)
''')

    def test_locked_cache_disables_new_writes_before_exceeding_budget(self):
        self.check('''
Snapshots.MAX_CACHE_BYTES=100+0x9c50
month=12012; tick=200; s:observe(); finishSnapshots()
require('code/snapshot-store').remove=function() return false,'file locked' end
month=12024; tick=300; s:observe(); finishSnapshots()
assert(s.disabled and captured==1 and #s.entries==1 and s.bytes==Snapshots.MAX_CACHE_BYTES)
assert(r.status=='playing')
''')

    def test_recovery_transition_retains_prior_cache_and_can_seek_back_across_clock_reset(self):
        self.check('''
local first=r.manifest
local second={id='recovered',startTick=50,lastTick=550,snapshotOriginMonth=12024}
first.nextReplay='recovered'; second.previousReplay='test'
ready.worlds={test={manifest=first},recovered={manifest=second}}
local recovered={manifest=second,worlds=ready.worlds}
require('code/replay-preparation').segment=function(first,id) assert(first==ready and id=='recovered'); return recovered end
s=Snapshots.new(r,ready); r.snapshots=s
month=12012; tick=400; s:observe(); finishSnapshots()
r.reset=function(self) assert(not self.snapshots); self.mode='none' end
r.startPlayback=function(self,id,_,actual,cached)
 self.mode='play'; self.status='playing'; self.manifest=actual.manifest
 tick=cached and cached.point.tick or actual.manifest.startTick
 self.snapshots=Snapshots.new(self,actual)
end
s:transition('recovered',ready.worlds)
assert(#s.entries==1 and #removed==0)
local position,total=s:progress(); assert(position==900 and total==1400)
s:request(0.25); assert(s.requestedId=='test' and s.requested==450)
s:advance(); assert(r.manifest==first and tick==400 and s.target==450)
assert(#s.entries==1 and #removed==0)
''')
