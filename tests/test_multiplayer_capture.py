"""Actual Lua file I/O: independent peers, snapshots, failures and recovery triage."""
import importlib.util
import json
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
import test_session_files

spec = importlib.util.spec_from_file_location('capture_inspector', Path(__file__).resolve().parents[1]/'tools/inspect_replay.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


class MultiplayerCaptureTests(unittest.TestCase):
    def test_periodic_host_and_client_snapshots_survive_named_prefix_and_bookmark_conversion(self):
        self.valid_world()
        self.lua.execute('''
local storage=require('code/snapshot-store'); local saved=0; local month=12000
require('code/platform').milliseconds=function() return 0 end
engine.calendarMonth=function() return month end
engine.saveSnapshot=function() error('Native multiplayer save is prohibited') end
require('code/world-capture').writeSnapshot=function(path,actual)
 assert(actual==engine and not trace.pendingTick and not trace.executing)
 saved=saved+1; local data=string.rep('world',400); store.write(path,data)
 return {bytes=#data,sha256=sha.sha256(data)}
end
for player=1,2 do
 month=12000; network.localPlayer=player; trace=Capture.new(engine,{})
 local copy
 for time=1,130 do
  now=time
  if time==10 then command() end
  if time==64 then month=12300 end
  tick(time)
  if time==65 then copy=trace:saveCopy('Embedded peer point') end
 end
 assert(saved==player)
 trace:observe('stop','match exit')
 local automatic=store.load(trace.lastCapture.id,profile)
 local named=store.load(copy.id,profile)
 for _,manifest in ipairs({automatic,named}) do
  assert(#manifest.snapshots==1 and manifest.snapshotOriginMonth==12000)
  local point=manifest.snapshots[1]; assert(point.tick==64 and point.commands==1 and not point.traceSequence)
  local ready=storage.prepare(manifest,point,storage.path(manifest,point))
  assert(ready.rng==engine:rngData())
  local r=require('code/replay-streams'):new({name=store.path(manifest.id)..'/stream'})
  r:openFiles('r'); r.mode='play'; r.tickFile=assert(io.open(store.path(manifest.id)..'/ticks.bin','rb'))
  r:restoreBookmark(point.bookmark)
  assert(r:peekCommand()==nil)
  assert(json:decode(r.rngFile:read()).time==64) -- point precedes its verification row
  assert(require('code/tick-journal').decode(r.tickFile:read(28)).time==64)
  r:reset()
 end
end
assert(nativeWrites==0)
''')

    def test_release_host_and_client_preserve_inputs_without_command_resource_snapshots(self):
        self.valid_world()
        self.lua.execute('''
require('code/build-profile').diagnostics=false
for player=1,2 do
 network.localPlayer=player; trace=Capture.new(engine,{})
 for time=1,2050 do
  tick(time)
  if time==50 then command() end
 end
 local copy=trace:saveCopy('Release prefix')
 trace:observe('stop','match exit')
 local manifest=store.load(trace.lastCapture.id,profile)
 assert(manifest.verificationProfile=='state-digest-v1' and manifest.commandCount==1)
 store.preflight(manifest); store.preflight(store.load(copy.id,profile))
 assert(#store.read(trace.lastCapture.path..'/ticks.bin')==2050*28)
 local checkpoints,commands=0,0
 for line in io.lines(trace.lastCapture.path..'/commands.jsonl') do
  local event=json:decode(line)
  if event.kind=='checkpoint' then
   checkpoints=checkpoints+1; assert(event.stateHash and not event.resources and not event.rngHash)
  elseif event.kind=='command' then
   commands=commands+1; assert(event.beforeRng and event.rng and not event.resources)
  end
 end
 assert(checkpoints==2 and commands==1)
end
assert(nativeWrites==0)
''')
        # This fixture models world construction; inspect the real journal and
        # sidecars without mistaking its placeholder world bytes for a native save.
        with patch.object(inspector, 'world_capture', return_value={'status': 'fixture'}):
            result = inspector.multiplayer_capture(self.path())
        self.assertEqual(result['journalFraming'], 'sealed', result)

    def test_recovery_keeps_calendar_cadence_and_embedded_worlds_in_both_named_segments(self):
        self.valid_world()
        self.lua.execute('''
local month=12000; local saved=0
engine.calendarMonth=function() return month end
require('code/platform').milliseconds=function() return 0 end
require('code/world-capture').writeSnapshot=function(path)
 saved=saved+1; local data=string.rep(tostring(saved),2000); store.write(path,data)
 return {bytes=#data,sha256=sha.sha256(data)}
end
for time=1,65 do
 if time==64 then month=12300 end
 tick(time)
end
local first=trace.capture.id; assert(saved==1)
network.syncStatus=1; now=66; trace:observe('immediateCommand','receive')
network.syncStatus=0; month=12350
for time=10,75 do
 if time==64 then month=12600 end
 tick(time)
 if time==10 then assert(saved==1,'Recovery start must not duplicate the first snapshot') end
end
assert(saved==2 and trace.capture.snapshotOriginMonth==12000)
local copy=trace:saveCopy('Recovery points'); trace:observe('stop','exit')
local storage=require('code/snapshot-store')
for _,id in ipairs({first,copy.id}) do
 local root=store.load(id,profile); local recovered=store.load(root.nextReplay,profile)
 assert(root.snapshotOriginMonth==12000 and recovered.snapshotOriginMonth==12000)
 for _,manifest in ipairs({root,recovered}) do
  assert(#manifest.snapshots==1 and manifest.snapshots[1].tick==64)
  storage.prepare(manifest,manifest.snapshots[1],storage.path(manifest,manifest.snapshots[1]))
 end
 assert(root.snapshots[1].worldHash~=recovered.snapshots[1].worldHash)
end
assert(nativeWrites==0)
''')

    def test_periodic_io_failure_does_not_stop_network_command_recording(self):
        self.valid_world()
        self.lua.execute('''
local month=12000; local attempted=0
engine.calendarMonth=function() return month end
require('code/platform').milliseconds=function() return 0 end
require('code/world-capture').writeSnapshot=function() attempted=attempted+1; error('disk full') end
for time=1,130 do
 now=time
 if time==64 then month=12300 end
 if time==70 then command() end
 tick(time)
end
assert(attempted==1 and trace.snapshots.disabled and not trace.failed)
trace:observe('stop','exit')
local manifest=store.load(trace.lastCapture.id,profile)
assert(manifest.commandCount==1 and not manifest.snapshots and nativeWrites==0)
''')

    def test_release_recovery_and_named_copy_keep_all_simulation_boundaries(self):
        self.lua.execute("require('code/build-profile').diagnostics=false; trace=Capture.new(engine,{})")
        self.test_recovery_links_and_named_copy_keep_both_worlds_independent()

    def test_tick_preflight_streams_split_frames_and_rejects_corrupt_tail(self):
        self.valid_world()
        self.lua.execute('''
local ticks=require('code/tick-journal'); local mp=require('code/multiplayer-session')
local p=temp_root..'/ticks-test'; assert(make_directory(p))
local data={}; local state=string.char(1,0,2,0,3,0,0,0,4,0,0,0)
for t=1,5000 do data[t]=ticks.frame(t,state,state) end
local raw=table.concat(data); store.write(p..'/ticks.bin',raw)
local digest=require('code/native-hash'); local real=digest.file; local passes=0
digest.file=function(...) passes=passes+1; return real(...) end
local manifest={multiplayer=network,startTick=1,lastTick=5001,ticksHash=hash_file(p..'/ticks.bin',mp.MAX_TICKS)}
local progress=0; mp.preflight(manifest,p,function() progress=progress+1 end)
assert(passes==1 and progress==3) -- 64 KiB boundaries split 28-byte frames
for _,bad in ipairs({raw:sub(1,-2),raw:sub(1,-29)..ticks.frame(4999,state,state)}) do
 store.write(p..'/ticks.bin',bad)
 manifest.ticksHash=hash_file(p..'/ticks.bin',mp.MAX_TICKS)
 assert(not pcall(mp.preflight,manifest,p))
end
digest.file=real
''')

    def setUp(self):
        test_session_files.SessionFileTests.setUp(self)
        self.lua.execute('''
require('code/native').profile=profile
Capture=require('code/multiplayer-capture'); Capture.ROOT=temp_root..'/captures'
now=1; single=false; reads={}; nativeWrites=0
core={readInteger=function(a) return reads[a] or 0 end,readByte=function() return 28 end,
 readString=function(_,n) return n==4 and string.char(1,0,2,0) or string.char(3,0,0,0,4,0,0,0) end,
 readBytes=function(_,n) local t={}; for i=1,n do t[i]=i%256 end; return t end,
 writeInteger=function() nativeWrites=nativeWrites+1; error('capture mutated game') end}
network={mode=1,localPlayer=1,syncStatus=0,handles={},roster={}}
for i=1,8 do
 network.handles[i]=i<=2 and 100+i or -1
 network.roster[i]={slot=i,kind=i<=2 and 'human' or 'empty',ai=0,variation=0}
end
engine={base=1000,rng=2000,sites={actorOffset=32},
 calendarMonth=function() return 12000 end,commandsPending=function() return false end,
 tick=function() return now end,player=function() return network.localPlayer end,
 singlePlayer=function() return single end,
 networkState=function() return json:decode(json:encode(network)) end,
 rngData=function() return string.rep('a',0x9c50) end,
 resourceData=function() return string.rep('r',800) end,
 rngState=function() return {1,2,3,4} end,resourceState=function() return resourceState() end}
store.settings=function()
 local raw='settings'; local env='environment'; local restart='resolved launch settings'
 return {raw=raw,hash=sha.sha256(raw),environment=env,environmentHash=sha.sha256(env),settingsCapture='resolved-v1',
 restartSettings=restart,restartSettingsHash=sha.sha256(restart)}
end
trace=Capture.new(engine,{multiplayerDiagnosticsEndTick=128,multiplayerDiagnosticsStartTick=64})
function tick(t)
 now=t; trace:observe('onTick'); assert(not trace.failed,trace.failureReason)
 now=t+1; trace:observe('afterTick'); now=t; assert(not trace.failed,trace.failureReason)
end
function command()
 reads[engine.base+0x2d824]=0; reads[engine.base+32]=network.localPlayer
 reads[engine.base+0x3c67c]=now; reads[engine.base+0x3c67c+4]=100+network.localPlayer
 trace:observe('receivedCommand',5000,1); trace:observe('beforeCommand'); trace:observe('afterCommand')
 assert(not trace.failed,trace.failureReason)
end
''')

    def path(self):
        return Path(self.lua.eval('trace.path or trace.lastCapture.path'))

    def valid_world(self):
        def hash_file(path, limit):
            self.assertLessEqual(Path(path).stat().st_size, limit)
            with open(path, 'rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()
        self.lua.globals().hash_file = hash_file
        self.lua.execute('''
store.ROOT=Capture.ROOT
core.readByte=function() return 34 end
engine.rngData=function()
 return string.char(1,0,2,0,123,0,0,0)..string.rep('a',40000)..string.char(3,0,0,0,4,0,0,0)
end
package.loaded['code/world-capture']={capture=function(path)
 for _,name in ipairs({'world.json','world.bin','world-layout.bin','world-header.bin'}) do store.write(path..'/'..name,'world') end
 return {status='complete',header=true,hash=sha.sha256('world')}
end}
''')

    def test_native_boundaries_seal_host_and_client_into_the_shared_replay_library(self):
        self.valid_world()
        self.lua.execute('''
for player=1,2 do
 network.localPlayer=player; trace=Capture.new(engine,{})
 for time=1,129 do
  if time==50 then now=time; command() end
  tick(time)
 end
 local copy=trace:saveCopy('Named prefix')
 trace:observe('stop','match exit')
 local manifest=store.load(trace.lastCapture.id,profile)
 assert(manifest.multiplayer.localPlayer==player and manifest.commandCount==1)
 assert(manifest.simulationProfile=='recorder-mp-v1' and manifest.status=='complete')
 store.preflight(manifest); store.preflight(store.load(copy.id,profile))
 local original=store.read(store.path(manifest.id)..'/ticks.bin')
 store.write(store.path(manifest.id)..'/ticks.bin',original:sub(1,-2))
 assert(not pcall(store.preflight,manifest))
end
assert(nativeWrites==0 and #store.list()==4)
''')

    def test_both_peers_capture_from_first_tick_ignore_window_and_save_full_tail(self):
        self.lua.execute('''
tick(1); first=trace.path; command(); tick(64); tick(128); tick(192); command()
assert(trace.file and not trace.closed and trace.capture.startTick==1)
now=200; tick(200); trace:observe('stop','normal exit')
assert(nativeWrites==0 and trace.lastCapture.status=='closed' and trace.lastCapture.lastObservedTick==200)
network.localPlayer=2; trace=Capture.new(engine,{}); tick(1); command(); tick(64)
trace:observe('stop','client exit'); second=trace.lastCapture.path
assert(second~=first)
''')
        for key, player, commands in [('first', 1, 2), ('second', 2, 1)]:
            path = Path(self.lua.eval(key))
            result = inspector.multiplayer_capture(path)
            self.assertEqual(result['journalFraming'], 'sealed', result)
            self.assertFalse(result['playable'])
            self.assertEqual(result['commands'], commands)
            self.assertEqual(json.loads((path/'capture.json').read_text())['initialNetwork']['localPlayer'], player)

    def test_named_snapshot_preserves_source_and_duplicate_names_never_overwrite(self):
        self.lua.execute('''
tick(1); command(); tick(64)
local original=store.read(trace.path..'/commands.jsonl')
a=trace:saveCopy('../same/name'); b=trace:saveCopy('../same/name')
assert(a.path~=b.path and a.sourceId==trace.capture.id and a.status=='snapshot')
assert(store.read(trace.path..'/commands.jsonl')==original and trace.file)
tick(128); command(); trace:observe('stop','exit')
assert(store.read(a.path..'/commands.jsonl')==original)
''')
        for key in ('a.path', 'b.path'):
            result = inspector.multiplayer_capture(self.lua.eval(key))
            self.assertEqual(result['journalFraming'], 'snapshot')
            self.assertEqual(result['commands'], 1)
        self.assertEqual(inspector.multiplayer_capture(self.path())['commands'], 2)

    def test_roster_sync_and_rewound_clock_start_a_replacement_world_after_synchronization(self):
        self.lua.execute('''
tick(1); first=trace.path; tick(64); tick(128)
network.syncStatus=1; tick(129)
network.handles[2]=-1; tick(130)
network.syncStatus=0; tick(64); command(); tick(128)
trace:observe('stop','after resynchronization')
assert(nativeWrites==0)
''')
        result = inspector.multiplayer_capture(self.path())
        self.assertEqual(result['journalFraming'], 'sealed', result)
        self.assertEqual(result['timelineSegments'], 1)
        self.assertEqual(result['commands'], 1)
        first = Path(self.lua.eval('first'))
        previous = json.loads((first/'capture.json').read_text())
        self.assertEqual(previous['nextReplay'], self.path().name)
        self.assertEqual(previous['lastObservedTick'], 128)
        self.assertGreaterEqual(inspector.multiplayer_capture(first)['coverageGaps'], 3)

    def test_crash_tail_is_reported_without_modifying_any_bytes(self):
        self.lua.execute('tick(1); command(); tick(64); trace.file:close(); trace.file=nil; trace.tickFile:close(); trace.tickFile=nil')
        path = self.path()
        stream = path/'commands.jsonl'
        valid = stream.read_bytes()
        stream.write_bytes(valid+b'{"kind":')
        before = stream.read_bytes()
        result = inspector.multiplayer_capture(path)
        self.assertEqual(result['journalFraming'], 'damaged')
        self.assertEqual(result['validPrefixBytes'], len(valid))
        self.assertEqual(result['commands'], 1)
        self.assertEqual(stream.read_bytes(), before)

    def test_command_after_clock_rewind_is_segmented_before_next_checkpoint(self):
        self.lua.execute('''
tick(1); first=trace.path; tick(64); tick(128); tick(190)
now=70; command(); tick(128); trace:observe('stop','exit')
''')
        result=inspector.multiplayer_capture(self.path())
        self.assertEqual(result['journalFraming'],'sealed',result)
        self.assertEqual(result['timelineSegments'],1)
        self.assertEqual(result['commands'],0)
        self.assertEqual(inspector.multiplayer_capture(self.lua.eval('first'))['commands'],1)

    def test_recovery_links_and_named_copy_keep_both_worlds_independent(self):
        self.valid_world()
        self.lua.execute('''
for time=1,65 do tick(time) end
local first=trace.capture.id
network.syncStatus=1; now=66; trace:observe('immediateCommand','receive')
network.syncStatus=0
for time=10,75 do tick(time) end
local second=trace.capture.id
assert(first~=second and trace.capture.previousReplay==first)
local copy=trace:saveCopy('Recovered prefix')
assert(copy.id~=first and copy.nextReplay~=second)
trace:observe('stop','exit')
local root=store.load(first,profile); local nextPart=store.load(root.nextReplay,profile)
assert(nextPart.id==second and nextPart.previousReplay==root.id)
store.preflight(root); store.preflight(nextPart)
store.preflight(store.load(copy.id,profile)); store.preflight(store.load(copy.nextReplay,profile))
assert(#store.list()==2 and nativeWrites==0)
''')

    def test_size_limit_stops_capture_only_and_preserves_flushed_prefix(self):
        self.lua.execute('''
tick(1); command(); tick(64); savedPath=trace.path
local before=store.read(trace.path..'/commands.jsonl')
Capture.MAX_BYTES=trace.bytes
now=128; trace:observe('onTick')
assert(trace.failed and not trace.file and nativeWrites==0)
assert(store.read(savedPath..'/commands.jsonl')==before)
assert(json:decode(store.read(savedPath..'/capture.json')).status=='interrupted')
trace:observe('beforeCommand'); trace:observe('afterCommand')
assert(nativeWrites==0)
''')
        result = inspector.multiplayer_capture(self.lua.eval('savedPath'))
        self.assertEqual(result['journalFraming'], 'unsealed prefix')

    def test_changed_sidecar_and_missing_sequence_are_not_accepted(self):
        self.lua.execute("tick(1); tick(64); tick(128); trace:observe('stop','exit')")
        path = self.path()
        (path/'environment.json').write_text('modified')
        stream = path/'commands.jsonl'
        lines = stream.read_bytes().splitlines(keepends=True)
        stream.write_bytes(lines[0]+b''.join(lines[2:]))
        result = inspector.multiplayer_capture(path)
        self.assertEqual(result['journalFraming'], 'damaged')
        self.assertIn('Missing or damaged environment.json', result['issues'])
        self.assertIn('Missing or repeated journal sequence', result['issues'])
