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

    def test_phase_observations_do_not_mislabel_viewer_pause_as_rng_divergence(self):
        a, b = self.sample(), self.sample()
        for rows in (a, b):
            for row in rows[:2]:
                row['phase'] = dict(tickReturns=0, unclockedReturns=0, clockJumps=0, navigationCountdown=100)
        b[0]['phase']['tickReturns'] = b[0]['phase']['unclockedReturns'] = 20
        b[1]['phase']['navigationCountdown'] = 90
        report = module.compare(self.write('a',a), self.write('b',b))
        self.assertEqual(report['status'], 'matching observed prefix')
        self.assertEqual(report['firstTickReturnDifference']['time'], 1)
        self.assertEqual(report['firstNavigationDifference']['time'], 64)
        del b[0]['phase']; del b[1]['phase']
        report = module.compare(self.write('a',a), self.write('b',b))
        self.assertNotIn('firstNavigationDifference', report)

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

    def test_spawn_context_distinguishes_players_even_with_equal_rng_counts(self):
        a, b = self.sample(), self.sample()
        for rows in (a,b):
            rows[0]['spawnContext'] = True
            rows[1]['spawns'] = [dict(time=63,caller=0x45b5e5,player=1,color=1,
                                     microX=120,microY=160,height=8,unitType=1)]
        b[1]['spawns'][0]['player'] = 2
        report = module.compare(self.write('a',a),self.write('b',b))
        self.assertEqual(report['status'],'attribution differs')
        self.assertTrue(report['spawnContextCompared'])
        self.assertEqual(report['callerDifferences'],[])
        self.assertEqual(report['secondSpawns'][0]['player'],2)
        del b[0]['spawnContext']
        report = module.compare(self.write('a',a),self.write('b',b))
        self.assertFalse(report['spawnContextCompared'])
        self.assertEqual(report['status'],'matching observed prefix')

    def test_claimed_spawn_context_requires_valid_interval_data(self):
        for invalid in (None,{},[{}],[dict(time=100,caller=1,player=1,color=1,
                                         microX=0,microY=0,height=0,unitType=1)]):
            rows = self.sample(); rows[0]['spawnContext'] = True; rows[1]['spawns'] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                module.trace(self.write('bad',rows))

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
