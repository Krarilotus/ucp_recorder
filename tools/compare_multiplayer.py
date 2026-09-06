"""Compare two peers' command traces. Exit 0=matched, 1=different, 2=incomplete."""
import argparse
import itertools
import json
import hashlib
import struct
from collections import Counter
from pathlib import Path


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('Invalid integer in trace')


def hash_value(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Missing or invalid SHA256 evidence')


def network_state(header):
    state = header.get('network')
    if not isinstance(state, dict) or state.get('mode') not in (1, 2) or state.get('syncStatus') != 0:
        raise ValueError('Missing network context or capture began during synchronization')
    integer(state['mode'], 1, 2)
    integer(state['syncStatus'], 0, 0)
    roster, handles = state.get('roster'), state.get('handles')
    if not isinstance(roster, list) or len(roster) != 8 or not isinstance(handles, list) or len(handles) != 8:
        raise ValueError('Missing eight-slot player roster')
    integer(state.get('localPlayer'), 1, 8)
    if header.get('localPlayer') != state['localPlayer']:
        raise ValueError('Inconsistent local player identity')
    used = set()
    for index, (player, handle) in enumerate(zip(roster, handles), 1):
        integer(handle, -2147483648, 2147483647)
        if not isinstance(player, dict) or player.get('slot') != index:
            raise ValueError('Invalid roster slot')
        integer(player.get('ai'), -2147483648, 2147483647)
        integer(player.get('variation'), -2147483648, 2147483647)
        kind = 'human' if handle != -1 else ('ai' if player['ai'] != 0 else 'empty')
        if player.get('kind') != kind:
            raise ValueError('Roster disagrees with native human/AI classification')
        if kind == 'human':
            if handle == 0 or handle in used:
                raise ValueError('Ambiguous or system-message player handle')
            used.add(handle)
    if roster[state['localPlayer'] - 1]['kind'] != 'human':
        raise ValueError('Local player is not an active human slot')
    return state


def rows(stream):
    # A fixed-buffer immediate message can contain 61,000 bytes encoded as hex.
    # Keep a bounded line reader while allowing that evidence plus JSON fields.
    while line := stream.readline(131073):
        if len(line) > 131072:
            raise ValueError('Oversized trace line')
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError('Invalid trace record')
        yield value


def capture_window(header):
    if header['format'] < 6:
        return None
    window = header.get('window')
    if not isinstance(window, dict):
        raise ValueError('Missing diagnostic window')
    first, last = window.get('startTick'), window.get('endTick')
    integer(last, 128, 2147483584)
    integer(first, 64, last - 64)
    if first % 64 or last % 64 or header.get('firstTick') != first:
        raise ValueError('Invalid or missed diagnostic start boundary')
    return dict(startTick=first, endTick=last)


def peer_pair(ah, bh):
    """Shared identity boundary for strict comparison and supplemental analyses."""
    for header in (ah, bh):
        if header.get('kind') != 'header':
            raise ValueError('Missing trace header')
        integer(header.get('format'), 1, 6)
        integer(header.get('localPlayer'), 1, 8)
        if header.get('variant') not in ('SHC', 'Extreme'):
            raise ValueError('Unknown game variant')
        if not isinstance(header.get('executable'), str) or not header['executable']:
            raise ValueError('Missing executable identity')
        if header['format'] >= 3:
            hash_value(header.get('environmentHash'))
        integer(header.get('firstTick', 0), 0, 2147483647)
    if any(ah.get(key) != bh.get(key) for key in ('variant', 'executable', 'format', 'firstTick')):
        raise ValueError('Traces require the same executable, variant, format and starting boundary')
    if ah['localPlayer'] == bh['localPlayer']:
        raise ValueError('Select traces from two different players')
    if ah['format'] >= 3 and ah['environmentHash'] != bh['environmentHash']:
        raise ValueError('Traces require the same resolved UCP settings, extension order/versions and framework')
    an = network_state(ah) if ah['format'] >= 4 else None
    bn = network_state(bh) if bh['format'] >= 4 else None
    aw, bw = capture_window(ah), capture_window(bh)
    if aw != bw:
        raise ValueError('Traces require the same diagnostic window')
    if an and (an['roster'] != bn['roster'] or an['mode'] != bn['mode']):
        raise ValueError('Traces require the same logical player roster and game mode')
    return an, bn, aw


def evidence(records, format_version, first_tick=0, network=None, window=None):
    count, command_count = 0, 0
    integer(first_tick, 0, 2147483647)
    previous_tick = first_tick
    next_checkpoint = (first_tick + 63) // 64 * 64
    for record in records:
        if record.get('kind') == 'gap':
            raise ValueError(f'Uncovered network event at tick {record.get("time")}: {record.get("reason")}')
        if record.get('kind') == 'end':
            if (record.get('status') != 'complete' or record.get('commands') != command_count or not count
                    or (format_version >= 2 and record.get('events') != count)):
                raise ValueError('Trace is incomplete or has no evidence')
            if window and (record.get('lastTick') != window['endTick']
                           or previous_tick != window['endTick']
                           or next_checkpoint != window['endTick'] + 64
                           or previous_kind != 'checkpoint'):
                raise ValueError('Missing diagnostic end checkpoint')
            if next(records, None) is not None:
                raise ValueError('Data follows trace completion')
            return
        allowed = ('command', 'checkpoint') if format_version >= 2 else ('command',)
        if record.get('kind') not in allowed:
            raise ValueError('Trace contains an untracked/unknown command')
        count += 1
        if record.get('sequence') != count:
            raise ValueError('Trace evidence sequence is incomplete')
        integer(record.get('time'), previous_tick, 2147483647)
        if window and record['time'] > window['endTick']:
            raise ValueError('Evidence outside diagnostic window')
        previous_tick = record['time']
        previous_kind = record['kind']
        if record['kind'] == 'command':
            command_count += 1
            if format_version >= 2 and record['time'] > next_checkpoint:
                raise ValueError('Missing periodic checkpoint evidence')
        fields = [('scheduledTime', 1, 2147483647),
                  ('player', 1, 8), ('category', 0, 127), ('size', 0, 1260)]
        if record['kind'] == 'command':
            for key, lo, hi in fields:
                integer(record.get(key), lo, hi)
            data = record.get('data')
            if not isinstance(data, str) or len(data) != record['size'] * 2 or any(c not in '0123456789abcdefABCDEF' for c in data):
                raise ValueError('Invalid trace payload')
            record['data'] = data.upper()
            if network is not None:
                player = record['player'] - 1
                if network['roster'][player]['kind'] != 'human' or record.get('handle') != network['handles'][player]:
                    raise ValueError('Command handle does not match its recorded logical player')
        elif record['time'] != next_checkpoint:
            raise ValueError('Missing, repeated or invalid checkpoint boundary')
        else:
            next_checkpoint += 64
            if format_version >= 3:
                hash_value(record.get('rngHash'))
        for key, length in [('rng', 4), ('resources', 200)]:
            values = record.get(key)
            if not isinstance(values, list) or len(values) != length:
                raise ValueError(f'Missing {key} evidence')
            for value in values:
                integer(value, -2147483648, 2147483647)
        yield record
    raise ValueError('Trace has no completion record')


def compare(left, right):
    difference = None
    count = 0
    try:
        with Path(left).open(encoding='utf-8') as a, Path(right).open(encoding='utf-8') as b:
            ar, br = rows(a), rows(b)
            ah, bh = next(ar), next(br)
            an, bn, window = peer_pair(ah, bh)
            for av, bv in itertools.zip_longest(evidence(ar, ah['format'], ah.get('firstTick', 0), an, window),
                                               evidence(br, bh['format'], bh.get('firstTick', 0), bn, window)):
                count += 1
                if difference:
                    continue  # Still validate both complete streams before reporting.
                if av is None or bv is None:
                    difference = dict(sequence=count, field='event count')
                    continue
                fields = ('kind', 'time')
                if av['kind'] == bv['kind'] == 'command':
                    fields += ('scheduledTime', 'player', 'category', 'size', 'data')
                elif av['kind'] == bv['kind'] == 'checkpoint' and ah['format'] >= 3:
                    fields += ('rngHash',)
                for key in fields + ('rng', 'resources'):
                    if av[key] == bv[key]:
                        continue
                    difference = dict(sequence=count, time=av['time'], field=key)
                    if key in ('rng', 'resources'):
                        index = next(i for i, (x, y) in enumerate(zip(av[key], bv[key])) if x != y)
                        difference.update(index=index, left=av[key][index], right=bv[key][index])
                        if key == 'resources':
                            difference.update(player=index // 25 + 1, resource=index % 25)
                    else:
                        difference.update(left=av[key], right=bv[key])
                    break
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
        return dict(status='incomplete', reason=str(error) or 'Empty trace', firstDifference=difference)
    return dict(status='different' if difference else 'matched', events=count, firstDifference=difference)


def inspect_trace(path):
    """Summarize evidence past coverage gaps; never returns a validation pass."""
    result = {'commands': 0, 'checkpoints': 0, 'gaps': 0, 'lastCheckpoint': None}
    commands, resources = hashlib.sha256(), hashlib.sha256()
    rng_streams = [hashlib.sha256(), hashlib.sha256()]
    callers, categories, gaps = Counter(), Counter(), Counter()
    def digest(target, value):
        target.update(json.dumps(value, separators=(',', ':'), sort_keys=True).encode())
        target.update(b'\n')
    try:
        with Path(path).open(encoding='utf-8') as stream:
            records = rows(stream)
            header = next(records)
            if header.get('kind') != 'header':
                raise ValueError('Missing header')
            result['localPlayer'] = header.get('localPlayer')
            result['rngAttribution'] = header.get('rngAttribution', False)
            ended = False
            for record in records:
                if ended:
                    raise ValueError('Data follows trace completion')
                kind = record.get('kind')
                if kind == 'command':
                    result['commands'] += 1
                    categories[(record['player'], record['category'])] += 1
                    digest(commands, [record.get(k) for k in
                        ('time', 'scheduledTime', 'player', 'category', 'size', 'data')])
                elif kind == 'checkpoint':
                    result['checkpoints'] += 1
                    result['lastCheckpoint'] = record['time']
                    digest(resources, [record['time'], record['resources']])
                    rng = record['rng']
                    if not isinstance(rng, list) or len(rng) != 4:
                        raise ValueError('Invalid RNG state')
                    for target, value, index in ((rng_streams[0], rng[0], rng[3]),
                                                  (rng_streams[1], rng[1], rng[2])):
                        digest(target, [record['time'], value, index])
                    callers.update(rng_call_counts(record.get('rngCalls', [])))
                elif kind == 'gap':
                    result['gaps'] += 1
                    gaps[(record.get('reason', ''), (record.get('details') or {}).get('category'))] += 1
                elif kind == 'end':
                    result['footer'] = record
                    ended = True
                elif kind != 'untracked':
                    raise ValueError('Unknown trace record')
            if not ended:
                result['inspectionError'] = 'Trace has no completion record'
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
        result['inspectionError'] = str(error) or 'Empty trace'
    result['timedCommandDigest'] = commands.hexdigest()
    result['resourceCheckpointDigest'] = resources.hexdigest()
    result['rngStreamDigests'] = [s.hexdigest() for s in rng_streams]
    result['commandCategories'] = [dict(player=p, category=c, count=n) for (p, c), n in sorted(categories.items())]
    result['gapCategories'] = [dict(reason=r, category=c, count=n) for (r, c), n in gaps.items()]
    result['rngCallers'] = [dict(stream=s, returnAddress=f'0x{a:08x}', count=n) for (s, a), n in sorted(callers.items())]
    return result


def native_sync_packets(path):
    """Decode command 12 evidence, never execute it or infer replay coverage."""
    packets = {}
    with Path(path).open(encoding='utf-8') as stream:
        records = rows(stream)
        header = next(records)
        if header.get('kind') != 'header' or header.get('immediatePayloadSource') != 'native-fixed-v1':
            raise ValueError('Native sync inspection requires corrected fixed-buffer evidence (0.21.0+)')
        integer(header.get('format'), 5, 6)
        state = network_state(header)
        ended, sequence, count = False, 0, 0
        for record in records:
            if ended:
                raise ValueError('Data follows trace completion')
            if record.get('kind') == 'end':
                if record.get('events') != sequence or record.get('status') not in ('complete', 'incomplete'):
                    raise ValueError('Incomplete sync evidence sequence')
                ended = True
                continue
            sequence += 1
            if record.get('sequence') != sequence:
                raise ValueError('Incomplete sync evidence sequence')
            details = record.get('details') or {}
            if record.get('kind') != 'gap' or details.get('category') != 12:
                continue
            if details.get('source') not in ('localImmediate', 'remoteImmediate'):
                raise ValueError('Unknown native sync dispatch source')
            player = details.get('player')
            integer(player, 1, 8)
            if state['roster'][player-1]['kind'] != 'human' or details.get('handle') != state['handles'][player-1]:
                raise ValueError('Native sync sender does not match player roster')
            data = details.get('data')
            if (details.get('size') != 10 or details.get('scheduledTime') != 0 or
                    not isinstance(data, str) or len(data) != 20 or
                    any(c not in '0123456789abcdefABCDEF' for c in data)):
                raise ValueError('Malformed native sync payload')
            lag, world_hash, match_tick = struct.unpack('<hIi', bytes.fromhex(data))
            integer(match_tick, 0, 2147483647)
            integer(record.get('time'), 0, 2147483647)
            key = (player, match_tick)
            if key in packets and packets[key]['hash'] != world_hash:
                raise ValueError('One sender advertised conflicting hashes for the same match tick')
            packets[key] = dict(hash=world_hash, lag=lag, observedTick=record['time'])
            count += 1
        if not ended:
            raise ValueError('Sync evidence has no completion record')
    return header, packets, count


def inspect_native_sync(left, right):
    result = {'purpose': 'Native advertised-hash evidence only; not replay validation'}
    try:
        ah, a, ac = native_sync_packets(left)
        bh, b, bc = native_sync_packets(right)
        peer_pair(ah, bh)
        common = a.keys() & b.keys()
        missing = a.keys() ^ b.keys()
        disagreements = sorted((key for key in common if a[key]['hash'] != b[key]['hash']),
                               key=lambda key: (key[1], key[0]))
        result.update(leftPackets=ac, rightPackets=bc, sharedAdvertisements=len(common),
                      unpairedAdvertisements=len(missing), receiptHashDifferences=len(disagreements))
        if disagreements:
            player, tick = disagreements[0]
            result['firstReceiptDifference'] = dict(player=player, matchTick=tick,
                left=f'{a[(player,tick)]["hash"]:08x}', right=f'{b[(player,tick)]["hash"]:08x}')
        # Only common advertisements with identical received hashes can be used
        # to compare different senders. Arrival ticks and lag are peer-local.
        by_tick = {}
        for player, tick in common:
            value = a[(player,tick)]['hash']
            if value and tick >= 10 and value == b[(player,tick)]['hash']:
                by_tick.setdefault(tick, {})[player] = value
        humans = {p['slot'] for p in ah['network']['roster'] if p['kind'] == 'human'}
        complete = {tick: values for tick, values in by_tick.items() if set(values) == humans}
        different = sorted(tick for tick, values in complete.items() if len(set(values.values())) > 1)
        result.update(allPlayerHashTicks=len(complete), differentHashTicks=len(different),
                      sameHashTicks=len(complete)-len(different))
        if different:
            tick = different[0]
            result['firstAdvertisedDifference'] = dict(matchTick=tick,
                hashes={str(p): f'{v:08x}' for p,v in sorted(complete[tick].items())})
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
        result['inspectionError'] = str(error) or 'Empty sync evidence'
    return result


def rng_call_counts(entries):
    if not isinstance(entries, list) or len(entries) > 512:
        raise ValueError('Missing or invalid RNG caller evidence')
    result = {}
    for entry in entries:
        integer(entry.get('stream'), 1, 2)
        integer(entry.get('returnAddress'), 0, 4294967295)
        integer(entry.get('count'), 1, 2147483647)
        key = entry['stream'], entry['returnAddress']
        if key in result:
            raise ValueError('Repeated RNG caller in checkpoint')
        result[key] = entry['count']
    return result


def rng_checkpoints(records, header, require_attribution=True):
    """Validate interval boundaries even when timed-replay coverage has gaps."""
    if header['format'] < 5 or (require_attribution and header.get('rngAttribution') is not True):
        raise ValueError('RNG interval inspection requires caller attribution (0.20.0+)')
    window = capture_window(header)
    next_tick = (header['firstTick'] + 63) // 64 * 64
    sequence, commands, gaps, checkpoints = 0, 0, 0, 0
    previous = header['firstTick']
    previous_kind = None
    for record in records:
        kind = record.get('kind')
        if kind == 'end':
            if (record.get('events') != sequence or record.get('commands') != commands
                    or record.get('status') not in ('complete', 'incomplete') or not checkpoints):
                raise ValueError('Incomplete RNG evidence footer')
            if gaps and record['status'] == 'complete':
                raise ValueError('RNG evidence footer omits coverage gaps')
            if window and (record.get('lastTick') != window['endTick']
                           or previous != window['endTick'] or previous_kind != 'checkpoint'):
                raise ValueError('Missing RNG inspection end checkpoint')
            if next(records, None) is not None:
                raise ValueError('Data follows trace completion')
            return
        sequence += 1
        if record.get('sequence') != sequence:
            raise ValueError('Incomplete RNG evidence sequence')
        integer(record.get('time'), previous, window['endTick'] if window else 2147483647)
        previous, previous_kind = record['time'], kind
        if kind == 'checkpoint':
            if record['time'] != next_tick:
                raise ValueError('Missing, repeated or invalid RNG checkpoint boundary')
            next_tick += 64
            for field, length in (('rng', 4), ('resources', 200)):
                values = record.get(field)
                if not isinstance(values, list) or len(values) != length:
                    raise ValueError('Missing ' + field + ' checkpoint evidence')
                for value in values:
                    integer(value, -2147483648, 2147483647)
            hash_value(record.get('rngHash'))
            counts = rng_call_counts(record.get('rngCalls')) if require_attribution else None
            checkpoints += 1
            yield record, counts
        elif kind == 'command':
            commands += 1
            if previous > next_tick:
                raise ValueError('Missing periodic RNG checkpoint')
        elif kind == 'gap':
            gaps += 1
            if previous > next_tick:
                raise ValueError('Missing periodic RNG checkpoint')
            if record.get('reason') in ('player roster or identity changed', 'native synchronization phase changed'):
                raise ValueError('RNG intervals span a player or synchronization transition')
        else:
            raise ValueError('Unknown RNG evidence event')
    raise ValueError('RNG evidence has no completion record')


def inspect_rng_intervals(left, right):
    """Locate caller-count differences; counts alone do not establish causality."""
    purpose = 'RNG interval observations only; not a desync cause or replay validation'
    result = {'purpose': purpose, 'alignedIntervals': 0, 'differentCallerIntervals': 0,
              'differentStateCheckpoints': 0, 'unpairedCheckpoints': 0}
    totals, changed_intervals = Counter(), Counter()
    try:
        with Path(left).open(encoding='utf-8') as a, Path(right).open(encoding='utf-8') as b:
            ar, br = rows(a), rows(b)
            ah, bh = next(ar), next(br)
            peer_pair(ah, bh)
            previous = None
            for av, bv in itertools.zip_longest(rng_checkpoints(ar, ah), rng_checkpoints(br, bh)):
                if av is None or bv is None:
                    result['unpairedCheckpoints'] += 1
                    continue
                ac, calls_a = av
                bc, calls_b = bv
                if ac['time'] != bc['time']:
                    raise ValueError('RNG checkpoint timelines differ')
                tick = ac['time']
                state_fields = [key for key in ('rng', 'rngHash', 'resources') if ac[key] != bc[key]]
                if state_fields:
                    result['differentStateCheckpoints'] += 1
                    result.setdefault('firstStateDifference', dict(time=tick, fields=state_fields,
                        leftRng=ac['rng'], rightRng=bc['rng']))
                # The first checkpoint starts the observation window. Its counters
                # have no preceding full interval and must not be compared as one.
                if previous is not None:
                    result['alignedIntervals'] += 1
                    differences = []
                    for key in sorted(calls_a.keys() | calls_b.keys()):
                        left_count, right_count = calls_a.get(key, 0), calls_b.get(key, 0)
                        if left_count == right_count:
                            continue
                        stream, address = key
                        differences.append(dict(stream=stream, returnAddress=f'0x{address:08x}',
                                                left=left_count, right=right_count))
                        totals[key] += right_count-left_count
                        changed_intervals[key] += 1
                    if differences:
                        result['differentCallerIntervals'] += 1
                        result.setdefault('firstCallerDifference', dict(afterTick=previous, throughTick=tick,
                                                                       callers=differences))
                previous = tick
        result['callersWithDifferences'] = [dict(stream=s, returnAddress=f'0x{address:08x}',
            rightMinusLeft=totals[(s,address)], differentIntervals=changed_intervals[(s,address)])
            for s,address in sorted(changed_intervals)]
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
        # Do not leave apparently complete counts after discovering a corrupt EOF.
        return dict(purpose=purpose, inspectionError=str(error) or 'Empty RNG evidence')
    return result


WORLD_DOMAINS = ('units', 'buildings', 'trees', 'tribes', 'playerData', 'mapState',
                 'tileMap', 'entities', 'moats', 'climbData', 'pitchDitches',
                 'unused', 'aivs', 'heatMaps')


def world_hash_samples(records, header):
    """Validate complete observation windows before returning any comparisons."""
    if header.get('nativeWorldHashes') != 'native-domains-v1':
        raise ValueError('Native world-hash inspection requires immediate subtotal capture (0.24.0+)')
    def checked_records():
        for record in records:
            if record.get('kind') == 'end':
                integer(record.get('pendingNativeHashes'), 0, 256)
                if record['pendingNativeHashes'] != 0:
                    raise ValueError('Unflushed native world-hash observations at trace end')
            yield record
    samples, duplicates = {}, 0
    previous_tick = header['firstTick']
    previous_checkpoint = header['firstTick']
    for checkpoint, _ in rng_checkpoints(checked_records(), header, require_attribution=False):
        entries = checkpoint.get('worldHashes')
        if not isinstance(entries, list) or len(entries) > 256:
            raise ValueError('Missing or oversized native world-hash evidence')
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'player', 'time', 'total', 'domains'}:
                raise ValueError('Malformed native world-hash observation')
            integer(entry['player'], 1, 8)
            if entry['player'] != header['localPlayer']:
                raise ValueError('Native world-hash observation belongs to another player')
            tick, total, domains = entry['time'], entry['total'], entry['domains']
            integer(tick, max(previous_tick, previous_checkpoint), checkpoint['time'])
            integer(total, 0, 4294967295)
            if not isinstance(domains, list) or len(domains) != 14:
                raise ValueError('Native world-hash observation requires 14 subtotals')
            for value in domains:
                integer(value, 0, 4294967295)
            if sum(domains) & 0xffffffff != total:
                raise ValueError('Native world-hash subtotal sum differs from total')
            if tick in samples:
                if samples[tick] != entry:
                    raise ValueError('Conflicting native world hashes for the same match tick')
                duplicates += 1
            samples[tick] = entry
            previous_tick = tick
        previous_checkpoint = checkpoint['time']
    return samples, duplicates


def inspect_world_hashes(left, right):
    purpose = 'Completed native world-hash observations only; not replay validation'
    try:
        with Path(left).open(encoding='utf-8') as a, Path(right).open(encoding='utf-8') as b:
            ar, br = rows(a), rows(b)
            ah, bh = next(ar), next(br)
            peer_pair(ah, bh)
            av, ad = world_hash_samples(ar, ah)
            bv, bd = world_hash_samples(br, bh)
        common = av.keys() & bv.keys()
        differences = sorted(t for t in common if av[t]['domains'] != bv[t]['domains'])
        result = dict(purpose=purpose, pairedTicks=len(common), differentTicks=len(differences),
                      sameTicks=len(common)-len(differences), leftUnpairedTicks=len(av.keys()-bv.keys()),
                      rightUnpairedTicks=len(bv.keys()-av.keys()), leftDuplicates=ad, rightDuplicates=bd)
        if differences:
            tick = differences[0]
            result['firstDifference'] = dict(matchTick=tick, leftPlayer=ah['localPlayer'],
                rightPlayer=bh['localPlayer'], leftTotal=av[tick]['total'], rightTotal=bv[tick]['total'],
                domains=[dict(domain=name, left=x, right=y) for name, x, y in
                         zip(WORLD_DOMAINS, av[tick]['domains'], bv[tick]['domains']) if x != y])
        return result
    except (OSError, ValueError, TypeError, KeyError, StopIteration, AttributeError) as error:
        return dict(purpose=purpose, inspectionError=str(error) or 'Empty native world-hash evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('--inspect', action='store_true',
                        help='Also summarize commands, gaps and RNG callers; does not relax validation or change exit codes')
    args = parser.parse_args()
    result = compare(args.left, args.right)
    if args.inspect:
        result['observations'] = {'left': inspect_trace(args.left), 'right': inspect_trace(args.right)}
        result['nativeSync'] = inspect_native_sync(args.left, args.right)
        result['rngIntervals'] = inspect_rng_intervals(args.left, args.right)
        result['worldHashes'] = inspect_world_hashes(args.left, args.right)
    print(json.dumps(result, indent=2))
    raise SystemExit({'matched': 0, 'different': 1, 'incomplete': 2}[result['status']])
