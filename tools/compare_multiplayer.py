"""Compare two peers' command traces. Exit 0=matched, 1=different, 2=incomplete."""
import argparse
import itertools
import json
import hashlib
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
    while line := stream.readline(65537):
        if len(line) > 65536:
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
            for header in (ah, bh):
                if header.get('kind') != 'header' or header.get('format') not in (1, 2, 3, 4, 5, 6):
                    raise ValueError('Unsupported trace format')
                if header['format'] >= 3:
                    hash_value(header.get('environmentHash'))
            if any(ah.get(key) != bh.get(key) for key in ('variant', 'executable', 'format')):
                raise ValueError('Traces require the same game executable, variant and format')
            if ah['format'] >= 3 and ah['environmentHash'] != bh['environmentHash']:
                raise ValueError('Traces require the same resolved UCP settings, extension order/versions and framework')
            an = network_state(ah) if ah['format'] >= 4 else None
            bn = network_state(bh) if bh['format'] >= 4 else None
            aw, bw = capture_window(ah), capture_window(bh)
            if aw != bw:
                raise ValueError('Traces require the same diagnostic window')
            if an and (an['roster'] != bn['roster'] or an['mode'] != bn['mode']):
                raise ValueError('Traces require the same logical player roster and game mode')
            for av, bv in itertools.zip_longest(evidence(ar, ah['format'], ah.get('firstTick', 0), an, aw),
                                               evidence(br, bh['format'], bh.get('firstTick', 0), bn, bw)):
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
    except (OSError, ValueError, KeyError, StopIteration) as error:
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
                    entries = record.get('rngCalls', [])
                    if not isinstance(entries, list) or len(entries) > 512:
                        raise ValueError('Invalid RNG caller evidence')
                    seen = set()
                    for entry in entries:
                        integer(entry.get('stream'), 1, 2)
                        integer(entry.get('returnAddress'), 0, 4294967295)
                        integer(entry.get('count'), 1, 2147483647)
                        key = (entry['stream'], entry['returnAddress'])
                        if key in seen:
                            raise ValueError('Repeated RNG caller in checkpoint')
                        seen.add(key)
                        callers[key] += entry['count']
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
    print(json.dumps(result, indent=2))
    raise SystemExit({'matched': 0, 'different': 1, 'incomplete': 2}[result['status']])
