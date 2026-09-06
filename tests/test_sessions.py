import hashlib
import unittest
import test_recorder as fixture


class SessionTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def test_attribution_starts_after_snapshot_and_flushes_before_desync(self):
        self.check('''
local r=session(); local events={}
r.rngTrace={observe=function(_,event,...)
 events[#events+1]=event
 if event=='begin' then assert(snapshots==1 and r.active and r.status=='recording') end
end}
r:startRecording(); assert(#events==0); r:activateRecording()
now=64; r:onTick(); assert(events[1]=='begin' and events[2]=='checkpoint')
r:reset(); assert(events[3]=='finish')
r.mode='play'; r.status='playing'; r.active=true; r.manifest={id='test',lastTick=128}
r.rngFile={read=function() return {time=64,rng={99,22,3,4}} end}
assert(not r:guard(function() r:onTick() end))
assert(events[4]=='checkpoint' and events[5]=='finish' and r.status=='error')
''')

    def test_failed_recording_can_resume_normal_game_but_never_seal_as_complete(self):
        self.check('''
local r=session(); r:beginMatch(); r:prepareRecording(); now=1; r:onTick()
local closed=0
for _,key in ipairs({'commandsFile','rngFile','infoFile'}) do
 r[key].close=function() closed=closed+1; error('close also failed') end
end
assert(not r:guard(function() error('capture failed') end))
assert(r.status=='error' and r.mode=='record' and not r.active and not scoped)
assert(memory[r.halt]==0 and paused and savedManifest.status=='failed' and closed==3)
local firstError=r.error
paused=false; now=100; r:onTick()
assert(not paused and r.manifest.lastTick==1)
assert(not r:guard(function() error('later failure') end) and r.error==firstError)
r:reset(); assert(savedManifest.status=='failed' and r.mode=='none')
''')

    def test_playback_report_replaces_success_on_failure_and_interruption(self):
        self.check('''
local r=session(); r.mode='play'; r.status='playing'; r.active=true
r.manifest={id='test'}; r.playedCommands=7; r.playbackStarted='attempt-2'; now=70
r:playbackResult('finished',{rngCheckpoints='matched'})
assert(lastEncoded.status=='finished')
r:playbackResult('playing')
assert(lastEncoded.status=='playing' and lastEncoded.rngCheckpoints==nil)
assert(lastEncoded.started=='attempt-2' and lastEncoded.commands==7)
assert(not r:guard(function() error('injected desync') end))
assert(lastEncoded.status=='failed' and lastEncoded.error:find('injected desync',1,true))
r.status='playing'; r:reset()
assert(lastEncoded.status=='interrupted' and r.mode=='none' and aborted)
''')

    def test_report_write_failure_still_cleans_up_interrupted_playback(self):
        self.check('''
local r=session(); r.mode='play'; r.status='playing'; r.active=true; r.manifest={id='test'}
require('code/sessions').write=function() error('disk full') end
assert(not pcall(function() r:reset() end))
assert(aborted and r.mode=='none' and not r.active and not scoped and memory[r.halt]==0)
''')

    def test_default_recording_arms_before_seed_and_saves_each_match(self):
        self.check('''
local r=session(); assert(r.autoRecord and not scoped)
r:beginMatch(); assert(r.status=='armed' and scoped and snapshots==0)
r:prepareRecording(); now=1; r:onTick(); assert(r.active and snapshots==1)
now=65; r:onTick(); r:reset(); assert(savedManifest.status=='complete' and savedManifest.lastTick==65)
r:beginMatch(); r:prepareRecording(); now=1; r:onTick(); assert(snapshots==2)
''')

    def test_default_recording_respects_disabled_loading_and_multiplayer(self):
        self.check('''
local r=session(); r.autoRecord=false; r:beginMatch(); assert(r.mode=='none')
r.autoRecord=true; engine.loading=true; r:beginMatch(); assert(r.mode=='none')
engine.loading=false; engine.singlePlayer=function() return false end
r:beginMatch(); assert(r.mode=='none' and not scoped)
engine.singlePlayer=function() return true end
r.mode='play'; r:beginMatch(); assert(r.mode=='play' and not scoped)
assert(not Session:new(engine,{autoRecord=false}).autoRecord)
''')

    def test_named_copy_flushes_source_and_keeps_recording_after_success_or_failure(self):
        self.check('''
local r=session(); r:beginMatch(); r:prepareRecording(); now=1; r:onTick()
local copies=0; local flushes=0
for _,key in ipairs({'commandsFile','rngFile','infoFile'}) do
 r[key].flush=function() flushes=flushes+1; return true end
end
require('code/sessions').copy=function(manifest,name,hash)
 assert(flushes==3 and name=='Stream' and manifest.lastTick==1 and #hash==64)
 copies=copies+1; return {id='copy'}
end
assert(r:saveCopy('Stream').id=='copy' and r.status=='recording' and r.active and scoped)
require('code/sessions').copy=function() error('Disk full') end
assert(not pcall(function() r:saveCopy('Stream') end))
now=2; r:onTick(); assert(r.manifest.lastTick==2 and r.status=='recording' and r.active)
assert(snapshots==1 and copies==1)
''')

    def test_start_callback_defers_snapshot_to_one_simulation_boundary(self):
        self.check('''
local r=session(); r:startRecording(); r:prepareRecording()
assert(snapshots==0 and not r.active)
now=1; r:onTick()
assert(snapshots==1 and r.active and r.manifest.startTick==1)
now=2; r:onTick(); assert(snapshots==1)
r:reset(); r:startRecording(); r:prepareRecording(); r:reset()
r:startRecording(); now=3; r:onTick()
assert(snapshots==1 and not r.active and not r.capturePending)
''')

    def test_pending_snapshot_is_cancelled_by_multiplayer_transition(self):
        self.check('''
local r=session(); r:startRecording(); r:prepareRecording()
engine.singlePlayer=function() return false end
now=1; r:onTick()
assert(snapshots==0 and not r.capturePending and r.mode=='none')
''')

    def test_full_rng_array_mismatch_halts_at_checkpoint_and_ending_boundary(self):
        self.lua.globals().hash_string = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.check('''
sha.sha256=hash_string
local original=engine:rngData()
local expected=sha.sha256(original)
-- Change an unconsumed byte while rngState() still returns the same four values.
engine.rngData=function() return original:sub(1,1000)..'y'..original:sub(1002) end
for _,tick in ipairs({64,65}) do
 local r=session(); r.mode='play'; r.status='playing'; r.active=true; r.playedCommands=0
 r.manifest={id='test',lastTick=tick,commandCount=0,finalRng={11,22,3,4},
   finalResources=resourceState(),finalRngHash=expected}
 r.rngFile={read=function() return {time=64,rng={11,22,3,4},resources=resourceState(),rngHash=expected} end}
 now=tick; assert(not r:guard(function() r:onTick() end))
 assert(r.firstDesync.kind=='rng-state' and r.firstDesync.time==tick and paused)
 assert(r.firstDesync.phase==(tick==64 and 'checkpoint' or 'ending state'))
end
''')

    def test_completion_hash_uses_last_observed_state_and_releases_buffer(self):
        self.lua.globals().hash_string = lambda value: hashlib.sha256(value.encode()).hexdigest()
        self.check('''
sha.sha256=hash_string
local r=session(); r:startRecording(); r:activateRecording(); now=65; r:onTick()
local expected=sha.sha256(engine:rngData())
engine.rngData=function() error('Must not read game state after leaving match') end
r:reset()
assert(savedManifest.finalRngHash==expected and not r.finalRngData)
''')

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
json.encode=function(_,value) lastEncoded=value; return 'json' end
sha={sha256=function(value) return string.rep('a',64) end}
savedManifest=nil
package.loaded['code/sessions']={
  new=function() return {id='test',variant='SHC',commandCount=0,lastTick=0} end,
  path=function(id) return 'ucp/replays/'..id end,
  save=function(value) savedManifest=value end,
  finish=function(value) value.status='complete'; savedManifest=value end,
  write=function() end, read=function() return 'data' end,
}
Session=require('code/session-recorder')
now=0; snapshots=0; space=true
engine={rng=0x1a279c0,
 rngData=function() return string.rep('x',0x9c50) end,
 resourceState=function() return resourceState() end,
 resetCommands=function(self) self.journal={executed=0} end,
 journal={executed=0},
 setScope=function(_,active) scoped=active end,
 singlePlayer=function() return true end,
 tick=function() return now end,
 player=function() return 1 end,
 rngState=function() return {11,22,3,4} end,
 saveSnapshot=function() snapshots=snapshots+1 end,
 pause=function() paused=true end,
 abortPlayback=function() aborted=true end,
 canSchedule=function() return space end,
 commandsPending=function() return false end,
 scheduleCommand=function(_,c) scheduled=scheduled+1 end,
}
core.readString=function() return string.rep('x',0x9c50) end
function session()
 local r=Session:new(engine)
 r.openFiles=function(self)
   local f={write=function(self) return self end,flush=function() return true end,close=function() return true end}
   self.commandsFile=f; self.rngFile=f; self.infoFile=f
 end
 return r
end
''')

    def test_arming_does_not_record_lobby_commands(self):
        self.check('''
local r=session(); r:startRecording()
r:onExecutedCommand(command(10))
assert(not r.active and snapshots==0 and r.manifest.commandCount==0)
r:activateRecording()
assert(r.active and snapshots==1 and r.manifest.status=='recording')
r:onExecutedCommand(command(10))
assert(r.manifest.commandCount==1)
''')

    def test_cancelled_lobby_is_not_a_completed_replay(self):
        self.check('''
local r=session(); r:startRecording(); r:reset()
assert(savedManifest.status=='cancelled' and r.mode=='none')
''')

    def test_recording_stop_preserves_completion_tick(self):
        self.check('''
local r=session(); r:startRecording(); r:activateRecording(); now=512; r:onTick(); now=513; r:reset()
assert(savedManifest.status=='complete' and savedManifest.lastTick==512)
''')

    def test_full_ring_does_not_consume_prefetched_command(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.playedCommands=0; r.manifest={player=1,variant='SHC'}; now=100; space=false
r.nextCommand=command(110); r:feed()
assert(scheduled==0 and r.nextCommand.time==110)
space=true; now=110; r.loadCommand=function() return nil end; r:feed()
assert(scheduled==1 and not r.nextCommand)
''')

    def test_late_command_stops_with_diagnostic(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true
now=100; r.nextCommand=command(99)
assert(not r:guard(function() r:feed() end))
assert(r.status=='error' and paused and memory[r.halt]==1 and scheduled==0)
''')

    def test_feed_waits_for_due_tick_and_rejects_a_full_ring_before_consuming(self):
        self.check('''
local r=session(); r.mode='play'; r.status='playing'; r.active=true; r.playedCommands=0
r.manifest={id='test',player=1}; r.nextCommand=command(110); r.loadCommand=function() return nil end
now=100; r:feed(); assert(scheduled==0 and r.nextCommand.time==110)
now=110; space=false
assert(not r:guard(function() r:feed() end))
assert(scheduled==0 and r.nextCommand.time==110 and aborted)
''')

    def test_recording_rejects_more_than_one_native_batch_at_the_same_tick(self):
        self.check('''
local r=session(); r:startRecording(); r:activateRecording()
for i=1,100 do r:onExecutedCommand(command(10)) end
assert(not r:guard(function() r:onExecutedCommand(command(10)) end))
assert(r.manifest.status=='failed')
''')

    def test_checkpoint_mismatch_halts_playback(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true
r.manifest={id='test',lastTick=512,commandCount=0}
r.rngFile={read=function() return {time=64,rng={11,22,3,999}} end}
now=64
assert(not r:guard(function() r:onTick() end))
assert(r.firstDesync.time==64 and r.status=='error' and memory[r.halt]==1)
''')

    def test_end_of_replay_requires_all_commands(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true
r.manifest={id='test',lastTick=65,commandCount=3}; r.playedCommands=2
now=65
assert(not r:guard(function() r:onTick() end)); assert(r.status=='error')
''')

    def test_final_checkpoint_boundary_finishes_without_next_checkpoint(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true; r.playedCommands=0
r.manifest={id='test',lastTick=64,commandCount=0,finalRng={11,22,3,4},finalResources=resourceState(),finalRngHash=string.rep('a',64)}
local reads=0
r.rngFile={read=function() reads=reads+1; assert(reads==1); return {time=64,rng={11,22,3,4},resources=resourceState(),rngHash=string.rep('a',64)} end}
now=64; r:onTick(); r:onTick()
assert(r.status=='finished' and paused and reads==1)
''')

    def test_queued_commands_are_not_reported_as_executed(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true; r.playedCommands=2
r.manifest={id='test',lastTick=65,commandCount=2,finalRng={11,22,3,4},finalResources=resourceState()}
engine.commandsPending=function() return true end
now=65; assert(not r:guard(function() r:onTick() end)); assert(r.status=='error')
''')

    def test_final_rng_is_checked_between_periodic_checkpoints(self):
        self.check('''
local r=session(); r.status='playing'; r.mode='play'; r.active=true; r.playedCommands=0
r.manifest={id='test',lastTick=65,commandCount=0,finalRng={11,22,3,5}}
now=65; assert(not r:guard(function() r:onTick() end)); assert(r.status=='error')
''')

    def test_write_failure_closes_streams_and_marks_failed(self):
        self.check('''
local r=session(); r:startRecording(); r:activateRecording()
local closed=0
r.commandsFile={write=function() return nil,'disk full' end,close=function() closed=closed+1; return true end}
assert(not r:guard(function() r:onExecutedCommand(command(10)) end))
assert(r.manifest.status=='failed' and not r.commandsFile and closed==1)
r:reset(); assert(savedManifest.status=='failed')
''')

    def test_close_failure_prevents_completion(self):
        self.check('''
local r=session(); r:startRecording(); r:activateRecording(); now=10; r:onTick()
r.commandsFile.close=function() return nil,'disk full' end
assert(not r:guard(function() r:reset() end)); assert(savedManifest.status=='failed')
''')

    def test_save_and_network_commands_are_not_replayed(self):
        self.check('''
local validation=require('code/validation')
for _,category in ipairs({2,14,39,46,89,95,109,121,122}) do
 local c=command(); c.commandCategory=category
 assert(not pcall(validation.sessionCommand,c,{player=1,variant='SHC'}))
end
local c=command(); c.commandCategory=119
c.size=8; c.data=string.rep('00',8)
assert(not pcall(validation.sessionCommand,c,{player=1,variant='SHC'}))
assert(pcall(validation.sessionCommand,c,{player=1,variant='Extreme'}))
''')

    def test_rejected_preflight_does_not_halt_a_later_normal_match(self):
        self.check('''
local r=session()
assert(not r:guard(function() error('damaged recording before native load') end))
assert(r.mode=='none' and memory[r.halt]==0 and not paused)
''')

    def test_failed_native_load_halts_even_before_playback_becomes_active(self):
        self.check('''
local r=session(); r.mode='play'; r.status='loading'; r.active=false
assert(not r:guard(function() error('load failed after native changes') end))
assert(memory[r.halt]==1 and paused)
''')

    def test_scope_is_only_enabled_for_requested_session_and_cleared_on_cancel(self):
        self.check('''
local r=session(); r:startRecording(); assert(scoped)
r:reset(); assert(not scoped)
engine.singlePlayer=function() return false end
assert(not r:guard(function() r:startRecording() end))
assert(not scoped and not paused and memory[r.halt]==0)
''')

    def test_mode_transition_aborts_capture_without_pausing_multiplayer(self):
        self.check('''
local r=session(); r:startRecording(); r:activateRecording(); now=64; r:onTick()
engine.singlePlayer=function() return false end
r:reconcileMode()
assert(r.mode=='none' and not scoped and not paused and memory[r.halt]==0)
assert(savedManifest.status=='failed')
''')

    def test_error_in_stale_playback_cannot_pause_multiplayer(self):
        self.check('''
local r=session(); r.mode='play'; r.active=true
engine.singlePlayer=function() return false end
assert(not r:guard(function() error('stale session') end))
assert(not paused and memory[r.halt]==0)
''')

    def test_resource_divergence_stops_even_when_rng_is_identical(self):
        self.check('''
local r=session(); r.mode='play'; r.status='playing'; r.active=true
r.manifest={id='test',lastTick=128}
r.rngFile={read=function() return {time=64,rng={11,22,3,4},resources=resourceState()} end}
engine.resourceState=function() local state=resourceState(); state[41]=5; return state end
now=64; assert(not r:guard(function() r:onTick() end))
assert(paused and r.status=='error' and r.firstDesync.kind=='resources')
assert(r.firstDesync.player==2 and r.firstDesync.resource==15 and r.firstDesync.actual==5)
''')

    def test_ending_resource_state_is_checked_between_checkpoints(self):
        self.check('''
local r=session(); r.mode='play'; r.status='playing'; r.active=true; r.playedCommands=0
r.manifest={id='test',lastTick=65,commandCount=0,finalRng={11,22,3,4},finalResources=resourceState()}
r.manifest.finalResources[200]=1
now=65; assert(not r:guard(function() r:onTick() end))
assert(r.status=='error' and r.firstDesync.player==8 and r.firstDesync.resource==24)
assert(r.firstDesync.phase=='ending state')
''')

    def test_starting_resource_mismatch_has_its_own_diagnostic(self):
        self.check('''
local r=session(); r.mode='play'; r.status='loading'; r.manifest={id='test'}
assert(not r:guard(function() r:checkResources(resourceState(1),'starting save') end))
assert(paused and r.firstDesync.phase=='starting save' and r.firstDesync.player==1)
''')
