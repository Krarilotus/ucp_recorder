import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('inspect_replay', Path(__file__).resolve().parents[1]/'tools/inspect_replay.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, records):
        path = self.root/name
        path.write_text(''.join(json.dumps(row)+'\n' for row in records), encoding='utf-8')
        return path

    def sample(self):
        return [dict(kind='header', format=1, replay='test', variant='SHC', executable='test', firstTick=1, rng=[1,2,3,4]),
                dict(kind='checkpoint', fromTick=1, time=64, count=1, order=17, rng=[1,3,4,4],
                     calls=[dict(stream=2, returnAddress=0x404f16, count=1, firstTick=63, lastTick=63)]),
                dict(kind='end', time=64, reason='finished')]

    def test_names_first_changed_caller_without_claiming_world_equality(self):
        first = self.write('first', self.sample())
        changed = self.sample()
        changed[1]['calls'][0]['count'] = changed[1]['count'] = 2
        report = module.compare(first, self.write('second', changed))
        self.assertEqual(report['status'], 'attribution differs')
        self.assertEqual(report['time'], 64)
        self.assertEqual(report['callerDifferences'][0]['returnAddress'], '0x00404F16')
        self.assertIn('do not prove', report['caution'])

    def test_unclosed_or_shorter_prefix_is_not_reported_as_complete_match(self):
        first = self.write('first', self.sample())
        second = self.write('second', self.sample()[:-1])
        report = module.compare(first, second)
        self.assertEqual(report['status'], 'matching observed prefix')
        self.assertFalse(report['secondClosed'])
        self.assertTrue(report['firstClosed'])

    def test_incompatible_start_and_damaged_counts_are_rejected(self):
        first = self.write('first', self.sample())
        for damage in ('start', 'count', 'gap', 'duplicate', 'format'):
            rows = self.sample()
            if damage == 'start': rows[0]['rng'][0] = 99
            if damage == 'format': rows[0]['format'] = 2
            if damage == 'count': rows[1]['count'] = 99
            if damage == 'gap': rows[1]['fromTick'] = 60
            if damage == 'duplicate': rows[1]['calls'] *= 2; rows[1]['count'] = 2
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                module.compare(first, self.write('second', rows))

    def test_legacy_failure_localizes_interval_and_preserves_modulo_caveat(self):
        self.write('manifest.json', [dict(id='test', startTick=1)])
        self.write('desync.json', [dict(time=22912, expected=[1051,8648,17170,4038], actual=[1051,11850,17165,4038])])
        self.write('stream-rng-sync.json', [dict(time=22848), dict(time=22912)])
        self.write('stream-commands.json', [dict(time=22714), dict(time=23000)])
        report = module.failure(self.root)
        self.assertEqual(report['detectionInterval'], [22848,22912])
        self.assertEqual(report['commandsInInterval'], [])
        self.assertEqual(report['rngIndexDifferenceModulo20000'], dict(stream1=0, stream2=19995))
        self.assertIn('not an exact call count', report['indexCaution'])
