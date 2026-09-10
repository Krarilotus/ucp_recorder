"""Exercise load transitions with the real session recorder and a fake game."""
import unittest
import test_sessions as fixture


class LoadLifecycleTests(unittest.TestCase):
    setUp = fixture.SessionTests.setUp
    check = fixture.SessionTests.check

    def prepare(self):
        self.check('''
engine.sites={packager=0x1000}
engine.loadedSkirmish=function(self) return self:singlePlayer() and eligible~=false end
r=session(); lifecycle=require('code/load-lifecycle').new(r)
''')

    def test_loaded_world_starts_at_its_own_tick_after_outer_handler(self):
        self.prepare()
        self.check('''
lifecycle:begin(); now=12345
assert(r.mode=='none' and not scoped and snapshots==0)
lifecycle:readComplete(0x1000)
assert(r.mode=='none' and snapshots==0) -- player identity/custom sections still being restored
lifecycle:finish()
assert(r.status=='armed' and r.capturePending and snapshots==0)
assert(r.manifest.origin=='loaded-save')
r:onTick(); assert(snapshots==1 and r.active and r.manifest.startTick==12345)
assert(r.manifest.rngHash==sha.sha256(engine:rngData()))
now=12400; r:onTick(); r:onMenuView(61)
assert(savedManifest.status=='complete' and savedManifest.lastTick==12400)
''')

    def test_repeated_load_seals_previous_world_before_replacement(self):
        self.prepare()
        self.check('''
for _,tick in ipairs({10000,500,99999}) do
 lifecycle:begin()
 if snapshots>0 then assert(savedManifest.status=='complete') end
 now=tick; lifecycle:readComplete(0x1000); lifecycle:finish(); r:onTick()
 assert(r.manifest.startTick==tick)
end
assert(snapshots==3)
''')

    def test_failed_reader_or_unrelated_packager_never_arms_recording(self):
        self.prepare()
        self.check('''
lifecycle:begin(); lifecycle:finish(); assert(r.mode=='none')
lifecycle:begin(); lifecycle:readComplete(0x2000); lifecycle:finish(); assert(r.mode=='none')
lifecycle:readComplete(0x1000); lifecycle:finish(); assert(r.mode=='none')
lifecycle:begin(); lifecycle:readComplete(0x1000); lifecycle:cancel(); lifecycle:finish()
assert(r.mode=='none' and snapshots==0 and not scoped)
''')

    def test_own_playback_restore_does_not_reset_or_arm_recording(self):
        self.prepare()
        self.check('''
r.mode='play'; r.status='loading'; engine.loading=true
lifecycle:begin(); lifecycle:readComplete(0x1000); lifecycle:finish()
assert(r.mode=='play' and r.status=='loading' and not r.capturePending)
assert(snapshots==0 and not scoped)
''')

    def test_disabled_capture_editor_campaign_and_multiplayer_are_excluded(self):
        self.prepare()
        self.check('''
for _,case in ipairs({'disabled','not skirmish','multiplayer'}) do
 r.autoRecord=case~='disabled'; eligible=case~='not skirmish'
 engine.singlePlayer=function() return case~='multiplayer' end
 lifecycle:begin(); lifecycle:readComplete(0x1000); lifecycle:finish()
 assert(r.mode=='none' and not scoped and snapshots==0)
end
''')

    def test_game_gate_checks_world_type_and_requested_view(self):
        self.prepare()
        self.check('''
engine.sites.gameCore=0x2000
local loaded=require('code/engine').loadedSkirmish
for _,current in ipairs({14,41}) do
 for _,mode in ipairs({0,1,2,3}) do
  for _,requested in ipairs({14,16,20,33,41}) do
   memory[0x2068]=mode; memory[0x200c]=current; memory[0x2018]=requested
   assert(loaded(engine)==(mode==3 and requested==14))
  end
 end
end
engine.singlePlayer=function() return false end
memory[0x2068]=3; memory[0x2018]=14; assert(not loaded(engine))
''')

    def test_completed_load_arms_while_load_dialog_is_still_displayed(self):
        self.prepare()
        self.check('''
engine.sites.gameCore=0x2000
engine.loadedSkirmish=require('code/engine').loadedSkirmish
lifecycle:begin(); now=94548
memory[0x2068]=3; memory[0x200c]=41; memory[0x2018]=14
lifecycle:readComplete(0x1000); lifecycle:finish()
assert(r.status=='armed' and r.capturePending and snapshots==0)
assert(r.manifest.origin=='loaded-save')
memory[0x200c]=14; r:onTick()
assert(r.active and snapshots==1 and r.manifest.startTick==94548)
now=100258; r:onTick(); r:onMenuView(61)
assert(savedManifest.status=='complete' and savedManifest.lastTick==100258)
''')
