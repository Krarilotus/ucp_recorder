"""Paired diagnostic evidence must identify separate peers and complete intervals."""
import copy
import json
import subprocess
import sys
import unittest

import test_multiplayer_trace as fixtures


class PairInspectionTests(unittest.TestCase):
    setUp = fixtures.CompareTraceTests.setUp
    compare = fixtures.CompareTraceTests.compare
    trace = fixtures.CompareTraceTests.trace
    full_trace = fixtures.CompareTraceTests.full_trace
    network_trace = fixtures.CompareTraceTests.network_trace
    bounded_trace = fixtures.CompareTraceTests.bounded_trace
    sync_pair = fixtures.CompareTraceTests.sync_pair

    def pair(self):
        a, b = self.bounded_trace(1), self.bounded_trace(2)
        for trace in (a, b):
            trace[0]['rngAttribution'] = True
            for checkpoint in trace[1:-1]:
                checkpoint['rngCalls'] = [dict(stream=1, returnAddress=0x471770, count=3)]
        return a, b

    def inspect(self, a, b):
        self.compare(a, b)
        return self.module.inspect_rng_intervals(self.root/'a.jsonl', self.root/'b.jsonl')

    def test_strict_comparison_rejects_same_peer_missing_and_invalid_identity(self):
        for version in range(1, 7):
            for invalid in (1, None, 0, 9, True, '2'):
                with self.subTest(version=version, invalid=invalid):
                    a, b = self.pair()
                    for trace in (a, b):
                        trace[0]['format'] = version
                    b[0]['localPlayer'] = invalid
                    b[0]['network']['localPlayer'] = invalid
                    result = self.compare(a, b)
                    self.assertEqual(result['status'], 'incomplete')
                    if invalid == 1 and type(invalid) is int:
                        self.assertIn('different players', result['reason'])

    def test_header_shape_errors_return_incomplete_instead_of_crashing(self):
        for key, invalid in (('network', []), ('network', 'bad'), ('format', True),
                             ('variant', None), ('executable', []), ('firstTick', {})):
            with self.subTest(key=key, invalid=invalid):
                a, b = self.pair()
                b[0][key] = invalid
                self.assertEqual(self.compare(a, b)['status'], 'incomplete')

    def test_native_sync_uses_the_same_pair_identity_boundary(self):
        for change in ('mode', 'format', 'environment', 'firstTick'):
            a, b = self.sync_pair()
            if change == 'mode': b[0]['network']['mode'] = 2
            elif change == 'format': b[0]['format'] = 99
            elif change == 'environment':
                for trace in (a, b): del trace[0]['environmentHash']
            else: b[0]['firstTick'] = 128
            self.compare(a, b)
            result = self.module.inspect_native_sync(self.root/'a.jsonl', self.root/'b.jsonl')
            self.assertIn('inspectionError', result, change)

    def test_rng_inspection_aligns_intervals_and_excludes_partial_first_counter(self):
        a, b = self.pair()
        b[1]['rngCalls'][0]['count'] = 900
        result = self.inspect(a, b)
        self.assertEqual(result['alignedIntervals'], 1)
        self.assertEqual(result['differentCallerIntervals'], 0)
        self.assertEqual(result['differentStateCheckpoints'], 0)
        self.assertEqual(result['callersWithDifferences'], [])

    def test_rng_inspection_reports_first_caller_and_state_difference_separately(self):
        a, b = self.pair()
        b[2]['rngCalls'][0]['count'] = 5
        b[2]['rng'][3] = 9
        b[2]['rngHash'] = 'c'*64
        result = self.inspect(a, b)
        self.assertEqual(result['firstCallerDifference'], dict(afterTick=64, throughTick=128,
            callers=[dict(stream=1, returnAddress='0x00471770', left=3, right=5)]))
        self.assertEqual(result['firstStateDifference']['time'], 128)
        self.assertEqual(result['firstStateDifference']['fields'], ['rng', 'rngHash'])
        self.assertEqual(result['callersWithDifferences'][0]['rightMinusLeft'], 2)

    def test_rng_caller_differences_are_not_erased_by_cancelling_totals(self):
        a, b = self.pair()
        for trace in (a, b):
            trace[0]['window']['endTick'] = 192
            trace.insert(-1, dict(copy.deepcopy(trace[2]), time=192, sequence=3))
            trace[-1].update(events=3, lastTick=192)
        b[2]['rngCalls'][0]['count'] = 5
        b[3]['rngCalls'][0]['count'] = 1
        result = self.inspect(a, b)
        self.assertEqual(result['differentCallerIntervals'], 2)
        self.assertEqual(result['callersWithDifferences'][0]['rightMinusLeft'], 0)
        self.assertEqual(result['callersWithDifferences'][0]['differentIntervals'], 2)

    def test_rng_inspection_handles_independent_callers_order_and_streams(self):
        a, b = self.pair()
        a[2]['rngCalls'] += [dict(stream=2, returnAddress=0x471770, count=7)]
        b[2]['rngCalls'] = [dict(stream=2, returnAddress=0x480000, count=2), b[2]['rngCalls'][0]]
        result = self.inspect(a, b)
        self.assertEqual(result['firstCallerDifference']['callers'], [
            dict(stream=2, returnAddress='0x00471770', left=7, right=0),
            dict(stream=2, returnAddress='0x00480000', left=0, right=2)])

    def test_incomplete_rng_evidence_never_leaves_apparently_complete_counts(self):
        for change in ('attribution', 'missing counter', 'duplicate caller', 'count', 'stream',
                       'address', 'sequence', 'checkpoint', 'footer', 'after footer', 'status',
                       'end tick', 'state', 'hash', 'transition', 'unknown', 'commands'):
            with self.subTest(change=change):
                a, b = self.pair()
                b[2]['rngCalls'][0]['count'] = 5
                if change == 'attribution': del b[0]['rngAttribution']
                elif change == 'missing counter': del b[2]['rngCalls']
                elif change == 'duplicate caller': b[2]['rngCalls'] *= 2
                elif change == 'count': b[2]['rngCalls'][0]['count'] = True
                elif change == 'stream': b[2]['rngCalls'][0]['stream'] = 3
                elif change == 'address': b[2]['rngCalls'][0]['returnAddress'] = -1
                elif change == 'sequence': b[2]['sequence'] = 4
                elif change == 'checkpoint': b.pop(2); b[-1]['events'] = 1
                elif change == 'footer': b.pop()
                elif change == 'after footer': b.append(b[2])
                elif change == 'status': b[-1]['status'] = 'failed'
                elif change == 'end tick': b[-1]['lastTick'] = 127
                elif change == 'state': b[2]['rng'] = [1]
                elif change == 'hash': b[2]['rngHash'] = 'z'*64
                elif change in ('transition', 'unknown'):
                    b.insert(2, dict(kind='gap' if change == 'transition' else 'other', time=65,
                                    sequence=2, reason='native synchronization phase changed'))
                    b[3]['sequence'] = 3; b[-1].update(events=3, status='incomplete')
                else: b[-1]['commands'] = 1
                result = self.inspect(a, b)
                self.assertIn('inspectionError', result)
                self.assertNotIn('alignedIntervals', result)

    def test_inspection_remains_supplemental_after_immediate_gap_and_cli_exits_incomplete(self):
        a, b = self.pair()
        for trace in (a, b):
            trace.insert(2, dict(kind='gap', sequence=2, time=65,
                reason='immediate command is outside timed replay coverage', details={'category': 12}))
            trace[3]['sequence'] = 3
            trace[-1].update(events=3, status='incomplete')
        result = self.inspect(a, b)
        self.assertEqual(result['alignedIntervals'], 1)
        run = subprocess.run([sys.executable, self.module.__file__, str(self.root/'a.jsonl'),
                              str(self.root/'b.jsonl'), '--inspect'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        output = json.loads(run.stdout)
        self.assertEqual(output['status'], 'incomplete')
        self.assertEqual(output['rngIntervals']['alignedIntervals'], 1)
