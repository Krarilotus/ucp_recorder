"""Compare two peers' command traces. Exit 0=matched, 1=different, 2=incomplete."""
import argparse
import itertools
import json
from pathlib import Path


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('Invalid integer in trace')


def hash_value(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Missing or invalid SHA256 evidence')


def rows(stream):
    while line := stream.readline(65537):
        if len(line) > 65536:
            raise ValueError('Oversized trace line')
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError('Invalid trace record')
        yield value


def evidence(records, format_version, first_tick=0):
    count, command_count = 0, 0
    integer(first_tick, 0, 2147483647)
    previous_tick = first_tick
    next_checkpoint = (first_tick + 63) // 64 * 64
    for record in records:
        if record.get('kind') == 'end':
            if (record.get('status') != 'complete' or record.get('commands') != command_count or not count
                    or (format_version >= 2 and record.get('events') != count)):
                raise ValueError('Trace is incomplete or has no evidence')
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
        previous_tick = record['time']
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
                if header.get('kind') != 'header' or header.get('format') not in (1, 2, 3):
                    raise ValueError('Unsupported trace format')
                if header['format'] >= 3:
                    hash_value(header.get('environmentHash'))
            if any(ah.get(key) != bh.get(key) for key in ('variant', 'executable', 'format')):
                raise ValueError('Traces require the same game executable, variant and format')
            if ah['format'] >= 3 and ah['environmentHash'] != bh['environmentHash']:
                raise ValueError('Traces require the same resolved UCP settings, extension order/versions and framework')
            for av, bv in itertools.zip_longest(evidence(ar, ah['format'], ah.get('firstTick', 0)),
                                               evidence(br, bh['format'], bh.get('firstTick', 0))):
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    args = parser.parse_args()
    result = compare(args.left, args.right)
    print(json.dumps(result, indent=2))
    raise SystemExit({'matched': 0, 'different': 1, 'incomplete': 2}[result['status']])
