import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import test_engine


class MultiplayerTraceTests(unittest.TestCase):
    check = test_engine.EngineTests.check
    command_hooks = test_engine.EngineTests.command_hooks

    def test_rng_attribution_is_bounded_sorted_and_does_not_consume_randomness(self):
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[9000]=0x600005; memory[9004]=0x45ce58
engine.trace.rngReturnAddresses={[0x600005]=0x471770}
engine.trace:observe('rngCall',1,9000)
engine.trace:observe('rngCall',1,9000)
engine.trace:observe('rngCall',2,9004)
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
local calls=traceRows[#traceRows].rngCalls
assert(#calls==2 and calls[1].stream==1 and calls[1].returnAddress==0x471770 and calls[1].count==2)
assert(calls[2].stream==2 and calls[2].count==1)
memory[0x1fe7da8]=192; engine.trace:observe('onTick')
assert(#traceRows[#traceRows].rngCalls==0 and calls[1].count==2)
for i=1,513 do memory[9000]=i; engine.trace:observe('rngCall',1,9000) end
assert(engine.trace.failed and engine.trace.failureReason:find('Too many RNG'))
assert(before().EDX==28) -- failure cannot suppress native gameplay
''')

    def test_rng_observer_filters_other_objects_and_singleplayer_and_preserves_registers(self):
        self.check('''
local read=core.readBytes
core.readBytes=function(a,n)
 if a==0x46a800 then return {139,129,76,156,0,0} end
 if a==0x46a7d0 then return {139,129,72,156,0,0} end
 return read(a,n)
end
require('code/rng-observer').install(engine.trace)
local regs={ECX=123,ESP=9000,EAX=42,EFLAGS=0xa83}
local get=core.readInteger
core.readInteger=function(a) assert(a~=9000,'unexpected RNG stack read'); return get(a) end
assert(callbacks[0x46a800](regs)==regs)
regs.ECX=engine.rng; memory[engine.base+0x618]=0
assert(callbacks[0x46a800](regs)==regs)
core.readInteger=get; memory[engine.base+0x618]=1
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[9000]=0x471770
assert(callbacks[0x46a800](regs)==regs)
assert(callbacks[0x46a7d0](regs)==regs)
assert(regs.EAX==42 and regs.EFLAGS==0xa83 and regs.ESP==9000 and regs.ECX==engine.rng)
assert(#engine.trace:rngEvidence()==2)
''')

    def test_immediate_payload_is_preserved_without_claiming_replay_coverage(self):
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[engine.base+0x2d830]=3; memory[address+4]=103
bytes[address+10]=0; bytes[address+11]=127; bytes[address+12]=255
engine.trace:observe('immediateCommand','remoteImmediate')
local event=traceRows[#traceRows]
assert(event.kind=='gap' and event.details.handle==103 and event.details.data=='007FFF')
memory[engine.base+0x2d830]=1261
engine.trace:observe('immediateCommand','remoteImmediate')
assert(engine.trace.failed and before().EDX==28)
''')

    def test_capture_status_survives_sealing_and_reports_failure(self):
        self.check('''
engine.trace=require('code/multiplayer-trace').new(engine,{multiplayerDiagnosticsStartTick=64,multiplayerDiagnosticsEndTick=128})
assert(engine.trace:statusLines()[1]:find('Waiting'))
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(engine.trace:statusLines()[1]:find('active'))
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(engine.trace.closed and engine.trace.lastResult.lastTick==128)
assert(engine.trace:statusLines()[3]:find('not being saved'))
engine.trace:observe('stop','mission exit')
assert(engine.trace:statusLines()[1]:find('saved'))
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(not engine.trace.lastResult and engine.trace:statusLines()[1]:find('active'))
engine.trace.file.write=function() return nil,'disk full' end
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(engine.trace:statusLines()[1]:find('stopped'))
''')

    def setUp(self):
        test_engine.EngineTests.setUp(self)
        self.command_hooks('record')
        self.check('''
package.loaded['code/platform']={mkdir=function() return true end}
require('code/sessions').settings=function() return {environmentHash=string.rep('a',64)} end
sha={sha256=function() return string.rep('b',64) end}
engine.rngData=function() return string.rep('x',0x9c50) end
traceRows={}; json.encode=function(_,v) traceRows[#traceRows+1]=v; return 'json' end
realNative.profile.name='SHC'; realNative.profile.sha256=string.rep('a',64)
engine.trace=require('code/multiplayer-trace').new(engine)
memory[engine.base+0x618]=1
memory[engine.base+engine.sites.actorOffset]=3
for slot=1,8 do memory[engine.base+0x6a8+slot*4]=100+slot end
memory[address+4]=103
recorder.active=false; recorder.mode='none'
engine.resourceState=function() return resourceState() end
core.writeInteger=function() error('diagnostics attempted native state write') end
function receive(size)
 memory[engine.base+0x2d830]=size or 1
 return callbacks[engine.sites.copySize.address]({ESI=engine.base,EDX=engine.buffer})
end
''')

    def test_trace_observes_resolved_remote_actor_without_changing_dispatch(self):
        self.check('''
assert(receive().EAX==1)
assert(before().EDX==28)
after()
engine.trace:observe('stop','test ended')
assert(#traceRows==3 and traceRows[1].kind=='header' and traceRows[3].status=='complete')
assert(traceRows[2].player==3 and traceRows[2].category==28 and traceRows[2].data=='01')
assert(traceRows[2].sequence==1 and #traceRows[2].resources==200)
assert(recorder.status=='recording' and #recorder.commands==0)
''')

    def test_trace_write_failure_cannot_suppress_multiplayer_command(self):
        self.check('''
receive(); assert(before().EDX==28)
engine.trace.file.write=function() return nil,'disk full' end
after()
assert(engine.trace.failed and not engine.trace.file)
assert(before().EDX==28 and receive().EAX==1)
assert(recorder.mode=='none' and not recorder.error)
''')

    def test_invalid_diagnostic_size_leaves_original_native_register_value(self):
        self.check('''
assert(receive(1261).EAX==1261 and engine.trace.failed)
assert(before().EDX==28)
''')

    def test_missing_receipt_or_interrupted_handler_marks_trace_incomplete(self):
        self.check('''
before(); after(); engine.trace:observe('stop','missing receipt')
assert(traceRows[2].kind=='untracked' and traceRows[3].status=='incomplete')
traceRows={}; receive(); before(); engine.trace:observe('stop','interrupted')
assert(traceRows[2].kind=='end' and traceRows[2].status=='incomplete')
''')

    def test_singleplayer_does_not_start_multiplayer_trace(self):
        self.check('''
memory[engine.base+0x618]=0; receive(); before(); after()
assert(#traceRows==0 and not engine.trace.file)
''')

    def test_tick_evidence_does_not_need_commands_and_deduplicates_paused_boundary(self):
        self.check('''
memory[0x1fe7da8]=64
engine.trace:observe('onTick'); engine.trace:observe('onTick')
assert(#traceRows==2 and traceRows[2].kind=='checkpoint' and traceRows[2].time==64)
assert(traceRows[1].format==5 and traceRows[1].environmentHash==string.rep('a',64))
assert(traceRows[2].rngHash==string.rep('b',64))
memory[0x1fe7da8]=65; engine.trace:observe('onTick'); assert(#traceRows==2)
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
engine.trace:observe('stop','test ended')
assert(traceRows[4].commands==0 and traceRows[4].events==2 and traceRows[4].status=='complete')
''')

    def test_full_rng_capture_failure_disables_observer_without_blocking_dispatch(self):
        self.check('''
memory[0x1fe7da8]=64
engine.rngData=function() error('RNG read failed') end
engine.trace:observe('onTick')
assert(engine.trace.failed and not engine.trace.file)
assert(receive().EAX==1 and before().EDX==28)
assert(recorder.mode=='none' and not recorder.error)
''')

    def test_roster_and_resync_transitions_between_checkpoints_are_not_omitted(self):
        self.check('''
memory[engine.base+0x6a8+8*4]=-1; memory[engine.base+0x714+8*4]=4
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(traceRows[1].network.roster[8].kind=='ai')
memory[0x1fe7da8]=65; memory[engine.base+0x6ac]=999
engine.trace:observe('onTick')
assert(traceRows[3].kind=='gap' and traceRows[3].reason=='player roster or identity changed')
memory[0x1fe7da8]=66; memory[engine.base+0xb98]=2
engine.trace:observe('onTick'); engine.trace:observe('stop','test ended')
assert(traceRows[4].reason=='native synchronization phase changed' and traceRows[5].status=='incomplete')
''')

    def test_native_immediate_observers_preserve_registers_and_expose_bypass(self):
        self.check('''
local sites=require('code/network-sites').SHC
local readBytes=core.readBytes
core.readBytes=function(address,size)
 for _,site in pairs(sites) do if address==site.address then assert(size==#site.bytes); return site.bytes end end
 return readBytes(address,size)
end
require('code/network-observer').install(engine.trace)
local regs={EAX=1,EBX=2,ECX=3,EDX=4,ESI=5,EDI=6,ESP=7,EBP=8,EFLAGS=0xa83}
assert(callbacks[sites.remoteImmediate.address](regs)==regs and #traceRows==0)
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
for name,site in pairs(sites) do
 if name=='remoteImmediate' or name=='localImmediate' then
  assert(callbacks[site.address](regs)==regs)
  assert(traceRows[#traceRows].kind=='gap' and traceRows[#traceRows].details.source==name)
 end
end
engine.trace.file.write=function() return nil,'disk full' end
assert(callbacks[sites.remoteImmediate.address](regs)==regs and engine.trace.failed)
assert(regs.EAX==1 and regs.EBX==2 and regs.ECX==3 and regs.EDX==4 and regs.ESI==5)
assert(regs.EDI==6 and regs.ESP==7 and regs.EBP==8 and regs.EFLAGS==0xa83)
''')

    def test_system_events_are_observed_before_host_or_roster_changes(self):
        self.check('''
local sites=require('code/network-sites').SHC
local readBytes=core.readBytes
core.readBytes=function(address,size)
 for _,site in pairs(sites) do if address==site.address then return site.bytes end end
 return readBytes(address,size)
end
require('code/network-observer').install(engine.trace)
local callback=callbacks[sites.systemMessage.address]
local regs={EAX=9,ECX=8,EDX=7,ESI=6,EDI=5,ESP=4,EBP=3,EBX=2,EFLAGS=0xa83}
memory[engine.base+0x2d81c]=12
memory[engine.base+0xcd8]=0x101
assert(callback(regs)==regs and #traceRows==0) -- before the capture window
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(callback(regs)==regs)
local host=traceRows[3]
assert(host.kind=='gap' and host.details.messageType==0x101 and host.details.source=='systemMessage')
assert(host.details.declaredSize==12 and host.details.removedHandle==nil)
-- No roster or sync change is needed for the system event itself to be visible.
memory[engine.base+0xcd8]=5; memory[engine.base+0xce0]=103
assert(callback(regs)==regs and traceRows[4].details.removedHandle==103)
memory[engine.base+0xcd8]=0x777 -- unknown events must not be silently whitelisted
assert(callback(regs)==regs and traceRows[5].kind=='gap')
engine.trace:observe('stop','test ended')
assert(traceRows[6].status=='incomplete')
assert(regs.EAX==9 and regs.ECX==8 and regs.EDX==7 and regs.ESI==6 and regs.EDI==5)
assert(regs.ESP==4 and regs.EBP==3 and regs.EBX==2 and regs.EFLAGS==0xa83)
''')

    def test_system_observer_never_reads_missing_handle_or_changes_singleplayer(self):
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[engine.base+0x2d81c]=4; memory[engine.base+0xcd8]=5
local readInteger=core.readInteger
core.readInteger=function(address)
 assert(address~=engine.base+0xce0,'read beyond declared header')
 return readInteger(address)
end
engine.trace:observe('systemMessage','systemMessage')
assert(traceRows[3].details.removedHandle==nil and not engine.trace.failed)
memory[engine.base+0x618]=0
engine.trace:observe('systemMessage','systemMessage')
assert(not engine.trace.file and #traceRows==4)
''')

    def test_invalid_system_size_or_write_failure_only_disables_diagnostics(self):
        for size in (0,3,61001):
            with self.subTest(size=size):
                self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[engine.base+0x2d81c]=%d
engine.trace:observe('systemMessage','systemMessage')
assert(engine.trace.failed and not engine.trace.file)
assert(before().EDX==28 and not recorder.error)
engine.trace:observe('stop','reset')
''' % size)
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[engine.base+0x2d81c]=4; memory[engine.base+0xcd8]=0x101
engine.trace.file.write=function() return nil,'disk full' end
engine.trace:observe('systemMessage','systemMessage')
assert(engine.trace.failed and not engine.trace.file and before().EDX==28)
''')

    def test_network_hook_conflict_cannot_partially_install_observers(self):
        self.check('''
local installed=0; core.detourCode=function() installed=installed+1 end
core.readBytes=function() return {} end
assert(not pcall(require('code/network-observer').install,engine.trace))
assert(installed==0)
''')

    def test_locally_queued_payload_does_not_require_receive_copy(self):
        self.check('''
engine.trace:observe('locallyQueuedCommand')
assert(before().EDX==28); after(); engine.trace:observe('stop','test ended')
assert(traceRows[2].kind=='command' and traceRows[2].origin=='local')
assert(traceRows[2].data=='01' and traceRows[3].status=='complete')
''')

    def test_invalid_local_payload_only_disables_diagnostics(self):
        self.check('''
memory[engine.base+0x2d830]=1261
engine.trace:observe('locallyQueuedCommand')
assert(engine.trace.failed and before().EDX==28 and not recorder.error)
''')


    def bounded(self, first=64, last=128):
        self.check('''
engine.trace=require('code/multiplayer-trace').new(engine,{
 multiplayerDiagnosticsStartTick=%d,multiplayerDiagnosticsEndTick=%d})
''' % (first,last))

    def test_bounded_window_keeps_earlier_receipts_and_seals_before_departure(self):
        self.bounded()
        self.check('''
memory[0x1fe7da8]=63; receive()
engine.trace:observe('onTick'); assert(#traceRows==0)
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(before().EDX==28); after()
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(#traceRows==5 and traceRows[1].format==6)
assert(traceRows[1].window.startTick==64 and traceRows[1].window.endTick==128)
assert(traceRows[3].kind=='command' and traceRows[3].data=='01')
assert(traceRows[5].status=='complete' and traceRows[5].lastTick==128)
assert(engine.trace.closed and not engine.trace.file)
-- Paused end boundary, later local orders, host departure and sync changes
-- cannot append to or reopen the already sealed interval.
engine.trace:observe('onTick'); receive(); assert(before().EDX==28); after()
memory[engine.base+0x6ac]=999; memory[engine.base+0xb98]=2
engine.trace:observe('systemMessage','systemMessage')
memory[0x1fe7da8]=192; engine.trace:observe('onTick')
assert(#traceRows==5 and not engine.trace.file and not engine.trace.failed)
''')

    def test_bounded_trace_rearms_only_after_session_reset(self):
        self.bounded()
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
engine.trace:observe('stop','new match')
memory[0x1fe7da8]=63; engine.trace:observe('onTick'); assert(#traceRows==4)
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(#traceRows==6 and traceRows[5].kind=='header' and traceRows[6].sequence==1)
''')

    def test_early_exit_and_skipped_boundaries_are_incomplete(self):
        for failure in ('early exit', 'late start', 'missed end'):
            with self.subTest(failure=failure):
                self.bounded()
                self.check("traceRows={}")
                if failure == 'late start':
                    self.check("memory[0x1fe7da8]=65; engine.trace:observe('onTick')")
                else:
                    self.check("memory[0x1fe7da8]=64; engine.trace:observe('onTick')")
                if failure == 'missed end':
                    self.check("memory[0x1fe7da8]=129; engine.trace:observe('onTick')")
                else:
                    self.check("engine.trace:observe('stop','mission exit')")
                self.check("assert(traceRows[#traceRows].status=='incomplete')")

    def test_window_does_not_hide_system_events_at_its_start(self):
        self.bounded()
        self.check('''
memory[0x1fe7da8]=64
memory[engine.base+0x2d81c]=4; memory[engine.base+0xcd8]=0x101
engine.trace:observe('systemMessage','systemMessage')
assert(traceRows[2].kind=='gap' and traceRows[2].details.messageType==0x101)
engine.trace:observe('onTick')
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(traceRows[#traceRows].status=='incomplete')
''')

    def test_bounded_capture_handles_ring_reuse_and_ai_roster(self):
        self.bounded()
        self.check('''
memory[engine.base+0x6a8+8*4]=-1; memory[engine.base+0x714+8*4]=4
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
for i=1,1200 do
 memory[engine.base+0x2d824]=(i-1)%200
 local ring=engine.base+0x3c67c+((i-1)%200)*1272
 memory[ring]=64; memory[ring+4]=103; memory[ring+8]=28
 memory[ring+10]=1
 receive(); assert(before().EDX==28); after()
end
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(traceRows[1].network.roster[8].kind=='ai')
assert(traceRows[#traceRows].status=='complete' and traceRows[#traceRows].commands==1200)
assert(traceRows[#traceRows].events==1202)
''')

    def test_invalid_bounded_options_are_rejected_before_observation(self):
        self.check('''
for _,pair in ipairs({{0,128},{64,64},{65,128},{64,129},{64,-1},{64,2147483648}}) do
 assert(not pcall(require('code/multiplayer-trace').new,engine,{
  multiplayerDiagnosticsStartTick=pair[1],multiplayerDiagnosticsEndTick=pair[2]}))
end
assert(#traceRows==0)
''')

    def test_failure_writing_window_footer_does_not_change_native_dispatch(self):
        self.bounded()
        self.check('''
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
local write=engine.trace.file.write
local calls=0
engine.trace.file.write=function(...)
 calls=calls+1
 if calls==2 then return nil,'disk full on footer' end
 return write(...)
end
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
assert(engine.trace.failed and not engine.trace.file)
assert(receive().EAX==1 and before().EDX==28)
assert(recorder.mode=='none' and not recorder.error)
''')


class CompareTraceTests(unittest.TestCase):
    def test_inspection_reports_evidence_after_gaps_without_relaxing_comparison(self):
        a = self.trace()
        a.insert(1, dict(kind='gap', time=10, reason='uncovered', details={'category': 12}))
        a.insert(3, dict(kind='checkpoint', time=64, resources=[0]*200, rng=[1,2,3,4],
                        rngCalls=[dict(stream=1, returnAddress=0x471770, count=3)]))
        self.assertEqual(self.compare(a, a)['status'], 'incomplete')
        result = self.module.inspect_trace(self.root/'a.jsonl')
        self.assertEqual(result['commands'], 1)
        self.assertEqual(result['gaps'], 1)
        self.assertEqual(result['rngCallers'], [dict(stream=1, returnAddress='0x00471770', count=3)])
        a[3]['rngCalls'] *= 2
        self.compare(a, a)
        self.assertIn('Repeated RNG', self.module.inspect_trace(self.root/'a.jsonl')['inspectionError'])

    def setUp(self):
        module_path = Path(__file__).resolve().parents[1] / 'tools/compare_multiplayer.py'
        spec = importlib.util.spec_from_file_location('compare_multiplayer', module_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def trace(self):
        return [dict(kind='header', format=1, variant='SHC', executable='a', localPlayer=1),
                dict(kind='command', sequence=1, time=10, scheduledTime=10, player=3,
                     category=28, size=1, data='01', handle=123, slot=0, rng=[1, 2, 3, 4], resources=[0] * 200),
                dict(kind='end', status='complete', commands=1)]

    def compare(self, a, b):
        paths = [self.root / 'a.jsonl', self.root / 'b.jsonl']
        for path, records in zip(paths, (a, b)):
            path.write_text(''.join(json.dumps(r) + '\n' for r in records), encoding='utf-8')
        return self.module.compare(*paths)

    def test_peer_local_identity_and_ring_slot_do_not_create_false_differences(self):
        a, b = self.trace(), self.trace()
        b[0]['localPlayer'] = 3
        b[1].update(handle=456, slot=199)
        self.assertEqual(self.compare(a, b)['status'], 'matched')

    def test_command_order_actor_tick_payload_rng_and_resources_are_compared(self):
        for key, value in [('time', 11), ('player', 2), ('data', 'FF'), ('rng', [1, 2, 3, 5]),
                           ('resources', [0] * 40 + [7] + [0] * 159)]:
            with self.subTest(key=key):
                a, b = self.trace(), self.trace()
                b[1][key] = value
                result = self.compare(a, b)
                self.assertEqual(result['status'], 'different')
                self.assertEqual(result['firstDifference']['field'], key)
                if key == 'resources':
                    self.assertEqual(result['firstDifference']['player'], 2)
                    self.assertEqual(result['firstDifference']['resource'], 15)

    def test_missing_footer_untracked_invalid_payload_and_empty_trace_are_incomplete(self):
        for change in ('footer', 'untracked', 'data', 'empty', 'sequence'):
            a, b = self.trace(), self.trace()
            if change == 'footer':
                b.pop()
            elif change == 'untracked':
                b[1]['kind'] = 'untracked'
            elif change == 'data':
                b[1]['data'] = 'GG'
            elif change == 'empty':
                b = []
            else:
                b[1]['sequence'] = 2
            self.assertEqual(self.compare(a, b)['status'], 'incomplete', change)

    def test_periodic_evidence_compares_without_any_commands(self):
        a = [dict(kind='header', format=2, variant='SHC', executable='a', firstTick=64),
             dict(kind='checkpoint', sequence=1, time=64, rng=[1, 2, 3, 4], resources=[0]*200),
             dict(kind='end', status='complete', events=1, commands=0)]
        b = json.loads(json.dumps(a))
        self.assertEqual(self.compare(a, b)['status'], 'matched')
        b[1]['rng'][3] = 5
        self.assertEqual(self.compare(a, b)['firstDifference']['field'], 'rng')

    def test_missing_checkpoint_cannot_be_hidden_in_a_matching_pair(self):
        a = self.trace()
        a[0].update(format=2, firstTick=0)
        a[-1].update(events=1)
        self.assertEqual(self.compare(a, a)['status'], 'incomplete')

    def full_trace(self):
        return [dict(kind='header', format=3, variant='SHC', executable='a', firstTick=64,
                     environmentHash='a'*64),
                dict(kind='checkpoint', sequence=1, time=64, rng=[1, 2, 3, 4],
                     resources=[0]*200, rngHash='b'*64),
                dict(kind='end', status='complete', events=1, commands=0)]

    def test_full_rng_difference_is_found_with_matching_values_and_indices(self):
        a, b = self.full_trace(), self.full_trace()
        self.assertEqual(self.compare(a, b)['status'], 'matched')
        b[1]['rngHash'] = 'c'*64
        self.assertEqual(self.compare(a, b)['firstDifference']['field'], 'rngHash')

    def test_different_environment_or_missing_full_rng_cannot_match(self):
        for change in ('environment', 'header hash', 'state hash', 'invalid hash'):
            a, b = self.full_trace(), self.full_trace()
            if change == 'environment':
                b[0]['environmentHash'] = 'c'*64
            elif change == 'header hash':
                del b[0]['environmentHash']
            elif change == 'state hash':
                del b[1]['rngHash']
            else:
                b[1]['rngHash'] = 'z'*64
            self.assertEqual(self.compare(a, b)['status'], 'incomplete', change)

    def network_trace(self):
        a = self.full_trace()
        a[0].update(format=4, localPlayer=1, network=dict(mode=1, localPlayer=1, syncStatus=0,
            handles=list(range(101,109)), roster=[dict(slot=i,kind='human',ai=0,variation=0) for i in range(1,9)]))
        return a

    def test_network_context_requires_unambiguous_roster_and_idle_sync(self):
        for change in ('missing', 'duplicate', 'system handle', 'classification', 'resync', 'local slot'):
            a, b = self.network_trace(), self.network_trace()
            n = b[0]['network']
            if change == 'missing': del b[0]['network']
            elif change == 'duplicate': n['handles'][2] = n['handles'][1]
            elif change == 'system handle': n['handles'][2] = 0
            elif change == 'classification': n['roster'][2]['kind'] = 'ai'
            elif change == 'resync': n['syncStatus'] = 2
            else: n['localPlayer'] = 3
            self.assertEqual(self.compare(a,b)['status'],'incomplete',change)

    def test_logical_roster_compares_across_transport_handle_renumbering(self):
        a, b = self.network_trace(), self.network_trace()
        for trace in (a,b):
            event=self.trace()[1]
            event.update(sequence=2,time=65,scheduledTime=65,handle=103)
            trace.insert(2,event); trace[-1].update(events=2,commands=1)
        b[0]['network']['handles'] = list(range(201,209)); b[2]['handle']=203
        b[0]['localPlayer']=3; b[0]['network']['localPlayer']=3
        self.assertEqual(self.compare(a,b)['status'],'matched')
        b[2]['handle']=202
        self.assertEqual(self.compare(a,b)['status'],'incomplete')

    def test_network_gaps_and_different_ai_rosters_cannot_report_match(self):
        a, b = self.network_trace(), self.network_trace()
        b[0]['network']['handles'][7]=-1; b[0]['network']['roster'][7].update(kind='ai',ai=4)
        self.assertEqual(self.compare(a,b)['status'],'incomplete')
        a.insert(2,dict(kind='gap',sequence=2,time=65,reason='immediate command'))
        a[-1].update(events=2,status='incomplete')
        result=self.compare(a,a)
        self.assertEqual(result['status'],'incomplete')
        self.assertIn('immediate command',result['reason'])

    def test_system_aware_format_does_not_accept_older_coverage_or_system_gaps(self):
        a,b=self.network_trace(),self.network_trace()
        a[0]['format']=5
        self.assertEqual(self.compare(a,b)['status'],'incomplete')
        b[0]['format']=5
        self.assertEqual(self.compare(a,b)['status'],'matched')
        a.insert(2,dict(kind='gap',sequence=2,time=65,
            reason='DirectPlay system message is outside replay coverage',details=dict(messageType=0x101)))
        a[-1].update(events=2,status='incomplete')
        result=self.compare(a,a)
        self.assertEqual(result['status'],'incomplete')
        self.assertIn('DirectPlay system message',result['reason'])

    def bounded_trace(self):
        trace = self.network_trace()
        trace[0].update(format=6,window=dict(startTick=64,endTick=128))
        trace.insert(2,dict(trace[1],sequence=2,time=128))
        trace[-1].update(events=2,lastTick=128)
        return trace

    def test_bounded_comparison_requires_the_final_checkpoint_even_if_both_traces_agree(self):
        a=self.bounded_trace()
        self.assertEqual(self.compare(a,a)['status'],'matched')
        for change in ('early end','missing checkpoint','command after end checkpoint','outside window',
                       'wrong first tick','misaligned start','missing window','missing last tick'):
            with self.subTest(change=change):
                a=self.bounded_trace()
                if change=='early end': a[-1]['lastTick']=64
                elif change=='missing checkpoint': del a[2]; a[-1]['events']=1
                elif change=='command after end checkpoint':
                    event=self.trace()[1]
                    event.update(time=128,scheduledTime=128,sequence=3,handle=103)
                    a.insert(3,event); a[-1].update(events=3,commands=1)
                elif change=='outside window': a[2]['time']=192
                elif change=='wrong first tick': a[0]['firstTick']=65
                elif change=='misaligned start': a[0]['window']['startTick']=65
                elif change=='missing window': del a[0]['window']
                else: del a[-1]['lastTick']
                self.assertEqual(self.compare(a,a)['status'],'incomplete')

    def test_bounded_peers_require_same_window_and_compare_ai_resources(self):
        a,b=self.bounded_trace(),self.bounded_trace()
        for trace in (a,b):
            trace[0]['network']['handles'][7]=-1
            trace[0]['network']['roster'][7].update(kind='ai',ai=4)
        b[0]['localPlayer']=3; b[0]['network']['localPlayer']=3
        self.assertEqual(self.compare(a,b)['status'],'matched')
        b[2]['resources'][175]=42
        result=self.compare(a,b)
        self.assertEqual(result['status'],'different')
        self.assertEqual(result['firstDifference']['player'],8)
        b[0]['window']['endTick']=192
        self.assertEqual(self.compare(a,b)['status'],'incomplete')
