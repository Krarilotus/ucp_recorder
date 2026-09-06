"""Fresh native subtotal capture and conservative paired diagnostic inspection."""
import copy
import unittest

import test_multiplayer_trace as fixtures


class WorldHashTraceTests(unittest.TestCase):
    setUp = fixtures.MultiplayerTraceTests.setUp
    check = fixtures.MultiplayerTraceTests.check
    command_hooks = fixtures.MultiplayerTraceTests.command_hooks

    def install(self):
        self.check('''
local site=require('code/world-hash-sites').SHC
local read=core.readBytes
core.readBytes=function(a,n) if a==site.address then assert(n==11); return site.bytes end; return read(a,n) end
require('code/world-hash-observer').install(engine.trace)
memory[0x1a275dc]=1
function hashSample(tick)
 memory[engine.base+0x7a8bc+engine:player()*4]=tick
 memory[engine.base+0x7a898+engine:player()*4]=90
 for i=0,13 do memory[engine.base+0x7a8e0+engine:player()*48+i*4]=i==0 and -1 or i end
end
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
''')

    def test_snapshot_survives_native_overlap_and_checkpoint_flush(self):
        self.install()
        self.check('''
hashSample(64)
local regs={ESI=engine.base,ECX=17,ESP=9000,EFLAGS=0xa83}
assert(callbacks[0x48da2e](regs)==regs and regs.EFLAGS==0xa83 and regs.ECX==17)
assert(not engine.trace.failed,engine.trace.failureReason)
local sample=engine.trace.pendingNativeHashes[1]
assert(sample.domains[1]==4294967295 and sample.total==90)
memory[engine.base+0x7a8e0+(engine:player()+1)*48]=999
memory[engine.base+0x7a8e0+(engine:player()+1)*48+4]=998
memory[0x1fe7da8]=128; engine.trace:observe('onTick')
local saved=traceRows[#traceRows].worldHashes
assert(#saved==1 and saved[1].domains[13]==12 and saved[1].domains[14]==13)
assert(traceRows[1].nativeWorldHashes=='native-domains-v1')
memory[0x1fe7da8]=192; engine.trace:observe('onTick')
assert(#traceRows[#traceRows].worldHashes==0 and #saved==1)
''')

    def test_inconsistent_sum_and_overflow_stop_diagnostics_only(self):
        for failure in ('sum', 'overflow'):
            self.setUp()
            self.install()
            self.check('hashSample(64)')
            if failure == 'sum':
                self.check('memory[engine.base+0x7a898+engine:player()*4]=91')
            else:
                self.check("for i=1,256 do engine.trace:observe('worldHash') end; assert(not engine.trace.failed)")
            self.check("engine.trace:observe('worldHash'); assert(engine.trace.failed and before().EDX==28)")

    def test_other_receivers_and_singleplayer_do_not_read_world_table(self):
        self.install()
        self.check('''
core.readInteger=function(a) assert(a==engine.base+0x618); return 0 end
local regs={ESI=engine.base+4}
assert(callbacks[0x48da2e](regs)==regs)
engine.trace.file=nil
regs.ESI=engine.base
assert(callbacks[0x48da2e](regs)==regs)
assert(not engine.trace.failed and #engine.trace.pendingNativeHashes==0)
''')

    def test_hook_conflict_installs_nothing(self):
        self.check('''
core.readBytes=function() return {} end
assert(not pcall(function() require('code/world-hash-observer').install(engine.trace) end))
assert(not callbacks[0x48da2e] and not engine.trace.nativeWorldHashes)
''')

    def test_unflushed_end_is_explicit_and_next_match_starts_empty(self):
        self.install()
        self.check('''
hashSample(64); engine.trace:observe('worldHash'); engine.trace:observe('stop','exit')
assert(traceRows[#traceRows].pendingNativeHashes==1)
memory[0x1fe7da8]=64; engine.trace:observe('onTick')
assert(#traceRows[#traceRows].worldHashes==0)
''')


class WorldHashInspectionTests(unittest.TestCase):
    setUp = fixtures.CompareTraceTests.setUp
    compare = fixtures.CompareTraceTests.compare
    trace = fixtures.CompareTraceTests.trace
    full_trace = fixtures.CompareTraceTests.full_trace
    network_trace = fixtures.CompareTraceTests.network_trace
    bounded_trace = fixtures.CompareTraceTests.bounded_trace

    def pair(self):
        a, b = self.bounded_trace(1), self.bounded_trace(2)
        for trace in (a, b):
            trace[0]['nativeWorldHashes'] = 'native-domains-v1'
            trace[1]['worldHashes'] = []
            trace[2]['worldHashes'] = [self.sample(trace[0]['localPlayer'], 80)]
            trace[-1]['pendingNativeHashes'] = 0
        return a, b

    def sample(self, player, tick):
        domains = [0xffffffff]+list(range(1,14))
        return dict(player=player, time=tick, total=sum(domains)&0xffffffff, domains=domains)

    def inspect(self, a, b):
        self.compare(a, b)
        return self.module.inspect_world_hashes(self.root/'a.jsonl', self.root/'b.jsonl')

    def test_pairing_uses_advertised_tick_and_reports_unpaired_and_duplicates(self):
        a, b = self.pair()
        a[2]['worldHashes'] *= 2
        a[2]['worldHashes'].append(self.sample(1,81))
        b[2]['worldHashes'].append(self.sample(2,82))
        result = self.inspect(a, b)
        self.assertEqual(result['pairedTicks'], 1)
        self.assertEqual(result['sameTicks'], 1)
        self.assertEqual(result['leftDuplicates'], 1)
        self.assertEqual(result['leftUnpairedTicks'], 1)
        self.assertEqual(result['rightUnpairedTicks'], 1)

    def test_domain_mismatches_survive_total_hash_collision(self):
        a, b = self.pair()
        b[2]['worldHashes'][0]['domains'][2:4] = [3, 2]
        result = self.inspect(a, b)
        difference = result['firstDifference']
        self.assertEqual(result['differentTicks'], 1)
        self.assertEqual(difference['matchTick'], 80)
        self.assertEqual(difference['leftTotal'], difference['rightTotal'])
        self.assertEqual(difference['domains'], [dict(domain='trees',left=2,right=3),dict(domain='tribes',left=3,right=2)])

    def test_empty_evidence_is_zero_pairs_and_never_replay_validation(self):
        a, b = self.pair()
        for trace in (a, b): trace[2]['worldHashes'] = []
        result = self.inspect(a, b)
        self.assertEqual(result['pairedTicks'], 0)
        self.assertNotIn('status', result)

    def test_corrupt_or_ambiguous_evidence_discards_partial_results(self):
        for change in ('marker', 'missing', 'oversized', 'shape', 'domain', 'total', 'sum', 'player',
                       'future', 'old', 'unordered', 'conflict', 'footer', 'pending', 'tail',
                       'transition', 'sequence', 'identity', 'checkpoint', 'pending bool'):
            with self.subTest(change=change):
                a, b = self.pair()
                entry = b[2]['worldHashes'][0]
                if change == 'marker': del b[0]['nativeWorldHashes']
                elif change == 'missing': del b[1]['worldHashes']
                elif change == 'oversized': b[2]['worldHashes'] *= 257
                elif change == 'shape': entry['extra'] = 1
                elif change == 'domain': entry['domains'][3] = True
                elif change == 'total': entry['total'] = -1
                elif change == 'sum': entry['total'] += 1
                elif change == 'player': entry['player'] = 1
                elif change == 'future': entry['time'] = 129
                elif change == 'old': entry['time'] = 63
                elif change == 'unordered': b[2]['worldHashes'].append(self.sample(2,79))
                elif change == 'conflict':
                    other = copy.deepcopy(entry); other['domains'][2:4] = [3,2]
                    b[2]['worldHashes'].append(other)
                elif change == 'footer': b.pop()
                elif change == 'pending': b[-1]['pendingNativeHashes'] = 1
                elif change == 'pending bool': b[-1]['pendingNativeHashes'] = False
                elif change == 'tail': b.append(copy.deepcopy(b[2]))
                elif change == 'sequence': b[2]['sequence'] = 4
                elif change == 'identity': b[0]['localPlayer'] = 1
                elif change == 'checkpoint': b.pop(1); b[1]['sequence'] = 1; b[-1]['events'] = 1
                else:
                    b.insert(2,dict(kind='gap',time=65,sequence=2,reason='player roster or identity changed'))
                    b[3]['sequence'] = 3; b[-1].update(events=3,status='incomplete')
                result = self.inspect(a,b)
                self.assertIn('inspectionError', result)
                self.assertNotIn('pairedTicks', result)

    def test_immediate_gaps_remain_incomplete_despite_equal_world_hashes(self):
        a,b = self.pair()
        for trace in (a,b):
            trace.insert(2,dict(kind='gap',sequence=2,time=70,reason='immediate command is outside timed replay coverage'))
            trace[3]['sequence']=3; trace[-1].update(events=3,status='incomplete')
        self.assertEqual(self.inspect(a,b)['sameTicks'],1)
        self.assertEqual(self.compare(a,b)['status'],'incomplete')
