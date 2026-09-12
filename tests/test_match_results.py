"""Natural result ownership, separate from replay viewing and old history."""
import unittest
import test_recorder as fixture
import test_sessions


class MatchResultTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        test_sessions.SessionTests.setUp(self)
        self.check('''
local Results=require('code/match-results')
local site=require('tests/fixtures/result-sites').SHC.insertion
core.detourCode=function(callback,address,size)
 assert(address==site.address and size==10); inserted=callback
end
r=session(); results=Results.new(r,site)
''')

    def test_natural_victory_and_defeat_seal_before_statistics_without_resampling(self):
        self.check('''
for _,view in ipairs({29,30}) do
 r:beginMatch(); r:prepareRecording(); now=1; r:onTick(); now=128; r:onTick()
 local manifest=r.manifest; now=99999
 results:onMenuView(view)
 assert(r.mode=='none' and not scoped and manifest.status=='complete' and manifest.lastTick==128)
 assert(results.pending==manifest)
 results:onMenuView(view); assert(results.pending==manifest)
 local registers={EBX=249}
 core.readString=function(address,size)
  assert(address==0xdf6250+249*0xbf0 and size==0xbf0); return 'inserted native result'
 end
 assert(inserted(registers)==registers and not results.pending)
 assert(manifest.nativeBattleHash==sha.sha256('inserted native result'))
 assert(savedManifest==manifest)
 inserted(registers) -- no second attachment
end
''')

    def test_playback_loading_history_and_abandoned_result_do_not_link_old_matches(self):
        self.check('''
r:beginMatch(); r:prepareRecording(); now=1; r:onTick()
for _,view in ipairs({14,16,58}) do results:onMenuView(view); assert(r.active) end
r.engine.loading=true; results:onMenuView(29); assert(r.active and not results.pending)
r.engine.loading=false
local manifest=r.manifest; r.mode='play'; results:onMenuView(29)
assert(r.active and not results.pending); r.mode='record'
results:onMenuView(30); assert(results.pending==manifest)
results:onMenuView(20); assert(not results.pending)
core.readString=function() error('No native history may be sampled') end
inserted({EBX=0})
results:onMenuView(29); inserted({EBX=0})
assert(not manifest.nativeBattleHash)
''')

    def test_each_multiplayer_capture_finishes_at_results_and_never_links_a_stale_capture(self):
        self.check('''
for _,status in ipairs({'complete','failed'}) do
 local manifest={id='peer',status=status}; local calls=0
 r.engine.trace={capture={id='peer'},observe=function(self,event,reason)
  assert(event=='stop' and reason=='native match results')
  calls=calls+1; self.capture=nil; self.lastReplay=manifest
 end}
 results:onMenuView(29)
 assert(calls==1 and results.pending==(status=='complete' and manifest or nil))
 results:onMenuView(20)
end
r.engine.trace={capture={id='new'},lastReplay={id='old',status='complete'},observe=function() end}
results:onMenuView(30); assert(not results.pending)
''')
