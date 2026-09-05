import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import test_engine


class MultiplayerTraceTests(unittest.TestCase):
    check = test_engine.EngineTests.check
    command_hooks = test_engine.EngineTests.command_hooks

    def setUp(self):
        test_engine.EngineTests.setUp(self)
        self.command_hooks('record')
        self.check('''
package.loaded['code/platform']={mkdir=function() return true end}
traceRows={}; json.encode=function(_,v) traceRows[#traceRows+1]=v; return 'json' end
realNative.profile.name='SHC'; realNative.profile.sha256=string.rep('a',64)
engine.trace=require('code/multiplayer-trace').new(engine)
memory[engine.base+0x618]=1
memory[engine.base+engine.sites.actorOffset]=3
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


class CompareTraceTests(unittest.TestCase):
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
