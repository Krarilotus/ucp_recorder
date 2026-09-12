"""Read-only failure triage and comparison of optional single-player RNG traces."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


WORLD_HEADER_FIELDS = [('description',1008),('timeAndHash',8),('players',28),('scenario',1017),('skirmish',80)]


def world_capture(folder, capture=None):
    """Verify bounded recorded descriptors and payload integrity; never dereference addresses."""
    folder = Path(folder)
    if capture is None:
        capture = json.loads((folder / 'capture.json').read_text(encoding='utf-8'))
    descriptor = capture.get('world', {})
    if descriptor.get('status') != 'complete':
        return {'status': 'unavailable', 'reason': descriptor.get('reason', 'Not captured by this version')}
    encoded = (folder / 'world.json').read_bytes()
    if len(encoded) > 1024 * 1024 or hashlib.sha256(encoded).hexdigest() != descriptor.get('hash'):
        raise ValueError('World manifest hash differs')
    world = json.loads(encoded)
    if (world.get('format') != 1 or world.get('kind') != 'native-world-evidence'
            or world.get('status') != 'complete' or world.get('tick') != capture.get('startTick')
            or any(world.get(k) != capture.get(k) for k in ('variant', 'executable'))):
        raise ValueError('World manifest identity differs')
    total=world.get('bytes')
    if world['variant'] not in ('SHC','Extreme') or type(total) is not int or not 0<total<=32*1024*1024:
        raise ValueError('Native world data length differs')
    table = (folder / 'world-layout.bin').read_bytes()
    if len(table) != 1968 or hashlib.sha256(table).hexdigest() != world.get('tableHash') or table[-16:] != bytes(16):
        raise ValueError('Native world layout differs')
    if (folder / 'world.bin').stat().st_size != total:
        raise ValueError('Native world data length differs')
    entries = world.get('sections')
    if not isinstance(entries, list) or len(entries) != 122:
        raise ValueError('Native world section count differs')
    offset = 0
    with (folder / 'world.bin').open('rb') as source:
        for i, entry in enumerate(entries):
            address, skip, size, compressed, section = struct.unpack_from('<IIIHH', table, i * 16)
            if (skip or not 0x400000<=address<address+size<0x80000000
                    or size>32*1024*1024 or offset+size>total or compressed not in (0,1)
                    or not isinstance(entry,dict) or any(entry.get(k) != v for k, v in dict(address=address, size=size,
                    compressed=compressed, section=section, offset=offset).items())):
                raise ValueError('Native world section descriptor differs')
            data = source.read(size)
            if len(data) != size or hashlib.sha256(data).hexdigest() != entry.get('sha256'):
                raise ValueError(f'Native world section {section} is damaged')
            offset += size
        if offset!=total or source.read(1):
            raise ValueError('Native world data length differs')
    header = world.get('header')
    if bool(header) != bool(descriptor.get('header')):
        raise ValueError('Native header presence differs')
    if header:
        data = (folder / 'world-header.bin').read_bytes()
        fields=[]
        offset=0
        for name,size in WORLD_HEADER_FIELDS:
            fields.append(dict(name=name,offset=offset,size=size))
            offset+=size
        if (header.get('format') != 1 or header.get('bytes') != offset or len(data) != offset
                or header.get('fields') != fields or hashlib.sha256(data).hexdigest() != header.get('sha256')):
            raise ValueError('Native save header is damaged')
    market = world.get('automarket')
    if bool(market) != bool(descriptor.get('automarket')):
        raise ValueError('Automarket snapshot presence differs')
    if market:
        data = (folder / 'automarket.bin').read_bytes()
        if (market.get('version') != '1.1.0' or market.get('format') != 2 or market.get('bytes') != 2416
                or len(data) != 2416 or data[:4] != b'\x02\0\0\0'
                or hashlib.sha256(data).hexdigest() != market.get('sha256')):
            raise ValueError('Automarket world state is damaged')
    return {'status': 'verified evidence', 'tick': world['tick'], 'bytes': total,
            'sections': entries, 'header': header, 'automarket': market, 'omissions': world.get('omissions', []),
            'caution': 'Raw native sections include local presentation state and padding. '
                       'Equal bytes do not establish complete extension coverage or working restoration.'}


def compare_worlds(first, second):
    a, b = world_capture(first), world_capture(second)
    if a['status'] != 'verified evidence' or b['status'] != 'verified evidence':
        raise ValueError('Both captures need verified world evidence')
    if a['tick'] != b['tick'] or [(e['section'], e['address'], e['size']) for e in a['sections']] != [
            (e['section'], e['address'], e['size']) for e in b['sections']]:
        raise ValueError('World variant or capture tick differs')
    differences = []
    with (Path(first) / 'world.bin').open('rb') as left, (Path(second) / 'world.bin').open('rb') as right:
        for x, y in zip(a['sections'], b['sections']):
            if x['sha256'] == y['sha256']:
                continue
            left.seek(x['offset']); right.seek(y['offset'])
            old, new = left.read(x['size']), right.read(y['size'])
            index = next(i for i, pair in enumerate(zip(old, new)) if pair[0] != pair[1])
            differences.append({'section': x['section'], 'size': x['size'], 'firstOffset': index,
                                'firstAddress': f"0x{x['address'] + index:08X}",
                                'firstBytes': [old[index], new[index]]})
    return {'tick': a['tick'], 'sectionsCompared': len(a['sections']), 'differences': differences,
            'automarketIdentical': a['automarket'] == b['automarket'],
            'caution': 'Section differences are investigation leads, not a desync verdict. '
                       'Automarket includes each PC\'s local editing slot (slot zero).'}


def multiplayer_capture(folder):
    """Inspect persisted evidence without repairing, truncating or claiming playback."""
    folder = Path(folder)
    manifest = json.loads((folder / 'capture.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != 'multiplayer-capture' or manifest.get('format') != 1:
        raise ValueError('Unsupported multiplayer capture')
    issues = []
    for name, field in [('ucp-config.yml', 'settingsHash'), ('environment.json', 'environmentHash'),
                        ('initial-rng.bin', 'rngHash'), ('replay-config.yml', 'restartSettingsHash')]:
        if field == 'restartSettingsHash' and not manifest.get(field):
            continue
        path = folder / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest.get(field):
            issues.append('Missing or damaged ' + name)
    try:
        world = world_capture(folder, manifest)
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        world = {'status': 'damaged', 'reason': str(error)}
        issues.append('World evidence: ' + str(error))
    sequence = commands = checkpoints = gaps = valid_bytes = 0
    segments = 1
    transitions = []
    categories = {}
    footer = None
    last_tick = manifest['startTick']
    verification = manifest.get('verificationProfile')
    if verification not in (None, 'state-digest-v1'):
        raise ValueError('Unsupported replay verification profile')
    interval = 1024 if verification else 64
    next_checkpoint = (last_tick + interval - 1) // interval * interval
    with (folder / 'commands.jsonl').open('rb') as stream:
        header_line = stream.readline(1024 * 1024)
        header = json.loads(header_line)
        if (header.get('kind') != 'header' or header.get('format') != 5
                or header.get('firstTick') != manifest['startTick']
                or header.get('network') != manifest['initialNetwork']
                or header.get('verificationProfile') != verification
                or any(header.get(k) != manifest.get(k) for k in ('variant', 'executable', 'environmentHash'))):
            raise ValueError('Capture header differs from its manifest')
        valid_bytes = len(header_line)
        while True:
            line = stream.readline(1024 * 1024)
            if not line:
                break
            if footer is not None:
                issues.append('Data follows capture footer'); break
            try:
                if not line.endswith(b'\n'):
                    raise ValueError('Interrupted or oversized journal row')
                row = json.loads(line)
                kind = row.get('kind')
                if kind == 'end':
                    if row.get('events') != sequence or row.get('commands') != commands:
                        raise ValueError('Footer counts differ from journal')
                    if row.get('status') not in ('complete', 'incomplete'):
                        raise ValueError('Invalid footer status')
                    footer = row
                else:
                    if row.get('sequence') != sequence + 1:
                        raise ValueError('Missing or repeated journal sequence')
                    tick = row.get('time')
                    rewind = kind == 'gap' and row.get('reason') == 'simulation clock moved backwards'
                    if type(tick) is not int or (tick < last_tick and not rewind):
                        raise ValueError('Timeline reset or invalid event tick')
                    if rewind:
                        previous_tick = row.get('details', {}).get('previousTick')
                        if type(previous_tick) is not int or tick >= previous_tick:
                            raise ValueError('Invalid timeline reset marker')
                        next_checkpoint = (tick + interval - 1) // interval * interval
                        segments += 1
                    if kind == 'checkpoint' and tick != next_checkpoint:
                        raise ValueError('Missing checkpoint boundary')
                    if kind not in ('command', 'untracked', 'checkpoint', 'gap'):
                        raise ValueError('Unknown journal event')
                    sequence += 1; last_tick = tick
                    if kind in ('command', 'untracked'):
                        commands += 1
                        key = str(row.get('category'))
                        categories[key] = categories.get(key, 0) + 1
                    elif kind == 'checkpoint':
                        checkpoints += 1; next_checkpoint += interval
                    else:
                        gaps += 1
                        if len(transitions) < 100 and 'immediate command' not in row.get('reason', ''):
                            transitions.append({'time': tick, 'reason': row.get('reason'), 'details': row.get('details')})
                valid_bytes += len(line)
            except (ValueError, TypeError, AttributeError) as error:
                issues.append(str(error)); break
    size = (folder / 'commands.jsonl').stat().st_size
    snapshot = manifest.get('status') == 'snapshot'
    if snapshot and (manifest.get('bytes') != size or manifest.get('events') != sequence
                     or manifest.get('commands') != commands):
        issues.append('Named snapshot boundary differs from journal')
    if manifest.get('status') == 'closed' and (footer is None or manifest.get('bytes') != size):
        issues.append('Closed capture is missing its committed ending')
    framing = 'damaged' if issues else ('snapshot' if snapshot else ('sealed' if footer else 'unsealed prefix'))
    return {'capture': manifest['id'], 'playable': False, 'journalFraming': framing,
            'compiledReplayStatus': manifest.get('replayStatus'),
            'compiledReplayReason': manifest.get('replayReason'),
            'note': 'This command inspects the raw capture. The game validates compiled replay streams before playback.',
            'issues': issues, 'validPrefixBytes': valid_bytes, 'fileBytes': size,
            'lastJournalTick': last_tick, 'events': sequence, 'commands': commands,
            'checkpoints': checkpoints, 'coverageGaps': gaps, 'timelineSegments': segments, 'commandCategories': categories,
            'transitions': transitions, 'footer': footer, 'world': world,
            'remainingPlaybackRequirements': manifest.get('missing', []),
            'caution': 'Journal framing and sidecar hashes are not command semantics or replay validation. '
                       'An unsealed prefix may come from an active game or a crash. Original files were not changed.'}


def rows(path):
    with Path(path).open(encoding="utf-8") as source:
        for number, line in enumerate(source, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}:{number}: incomplete or invalid JSON") from error


def failure(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    desync = json.loads((folder / "desync.json").read_text(encoding="utf-8"))
    tick = desync["time"]
    previous = None
    for row in rows(folder / "stream-rng-sync.json"):
        if row["time"] >= tick:
            break
        previous = row
    commands = list(rows(folder / "stream-commands.json"))
    start = previous["time"] if previous else manifest["startTick"]
    result = {"replay": manifest["id"], "failure": desync,
              "previousCheckpoint": start, "detectionInterval": [start, tick],
              "commandsInInterval": [c for c in commands if start < c["time"] <= tick],
              "precedingCommands": [c for c in commands if c["time"] <= start][-10:],
              "caution": "Checkpoint detection interval does not date the first world-state difference."}
    expected, actual = desync.get("expected"), desync.get("actual")
    if isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual) == 4:
        result["rngIndexDifferenceModulo20000"] = {
            "stream1": (actual[3] - expected[3]) % 20000,
            "stream2": (actual[2] - expected[2]) % 20000,
        }
        result["indexCaution"] = "Indices advance modulo 20000; their difference alone is not an exact call count."
    return result


def trace(path):
    entries = list(rows(path))
    if not entries or entries[0].get("kind") != "header" or entries[0].get("format") not in (1, 2):
        raise ValueError(f"{path}: unsupported or missing attribution header")
    checkpoints = [e for e in entries if e.get("kind") == "checkpoint"]
    previous = entries[0]["firstTick"]
    for entry in checkpoints:
        if entry["fromTick"] != previous or entry["time"] < previous:
            raise ValueError(f"{path}: non-contiguous attribution checkpoints")
        keys = [(c["stream"], c["returnAddress"]) for c in entry["calls"]]
        if len(set(keys)) != len(keys) or sum(c["count"] for c in entry["calls"]) != entry["count"]:
            raise ValueError(f"{path}: inconsistent attribution counts")
        for flag, field, limit, fields in (
                ('spawnContext', 'spawns', 512, ('color', 'unitType')),
                ('fireContext', 'fires', 2048, ('spreadParameter', 'intensity'))):
            if not entries[0].get(flag):
                continue
            events = entry.get(field)
            if not isinstance(events, list) or len(events) > limit:
                raise ValueError(f"{path}: missing or oversized {field} context")
            for event in events:
                keys = ('time', 'caller', 'player', 'microX', 'microY', 'height') + fields
                if not isinstance(event, dict) or any(type(event.get(key)) is not int for key in keys):
                    raise ValueError(f"{path}: malformed {field} context")
                if flag == 'fireContext' and event.get('kind') not in ('ignite', 'spread'):
                    raise ValueError(f"{path}: malformed fire kind")
                if not entry["fromTick"] <= event["time"] <= entry["time"]:
                    raise ValueError(f"{path}: {field} outside its checkpoint interval")
        previous = entry["time"]
    return entries[0], checkpoints, entries[-1].get("kind") == "end"


def compare(first, second):
    a_header, a_rows, a_complete = trace(first)
    b_header, b_rows, b_complete = trace(second)
    for key in ("format", "replay", "variant", "executable", "firstTick", "rng"):
        if a_header[key] != b_header[key]:
            raise ValueError(f"Attribution starting {key} differs")
    result = {"firstClosed": a_complete, "secondClosed": b_complete,
              "status": "matching observed prefix", "checkpointsCompared": 0,
              "caution": "Caller counts and the ordering checksum do not prove equal world state."}
    with_spawns = bool(a_header.get("spawnContext") and b_header.get("spawnContext"))
    result["spawnContextCompared"] = with_spawns
    with_fires = bool(a_header.get('fireContext') and b_header.get('fireContext'))
    result['fireContextCompared'] = with_fires
    def phase_difference(a, b, time):
        if a.get("phase") is None or b.get("phase") is None:
            return
        for label, keys in (("firstNavigationDifference", ("navigationCountdown",)),
                            ("firstTickReturnDifference", ("tickReturns", "unclockedReturns", "clockJumps"))):
            left, right = ({key: row["phase"][key] for key in keys} for row in (a, b))
            if label not in result and left != right:
                result[label] = {"time": time, "first": left, "second": right,
                    "caution": "Return counts include viewer-paused entry returns; this is an observation, not a desync cause."}

    phase_difference(a_header, b_header, a_header["firstTick"])
    for a, b in zip(a_rows, b_rows):
        if (a["fromTick"], a["time"]) != (b["fromTick"], b["time"]):
            result.update(status="different checkpoint boundaries", first=a["time"], second=b["time"])
            return result
        result["checkpointsCompared"] += 1
        phase_difference(a, b, a["time"])
        if (any(a[key] != b[key] for key in ("count", "order", "rng", "calls"))
                or (with_spawns and a["spawns"] != b["spawns"])
                or (with_fires and a['fires'] != b['fires'])):
            def callers(row):
                return {(c["stream"], c["returnAddress"]): c for c in row["calls"]}
            left, right = callers(a), callers(b)
            differences = []
            for key in sorted(left.keys() | right.keys()):
                if left.get(key) != right.get(key):
                    differences.append({"stream": key[0], "returnAddress": f"0x{key[1]:08X}",
                                        "first": left.get(key), "second": right.get(key)})
            result.update(status="attribution differs", fromTick=a["fromTick"], time=a["time"],
                          callerDifferences=differences, firstRng=a["rng"], secondRng=b["rng"],
                          firstOrder=a["order"], secondOrder=b["order"])
            if with_spawns:
                result.update(firstSpawns=a["spawns"], secondSpawns=b["spawns"])
            if with_fires:
                result.update(firstFires=a['fires'], secondFires=b['fires'])
            return result
    result["unpairedCheckpoints"] = abs(len(a_rows) - len(b_rows))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("failure").add_argument("replay_folder", type=Path)
    sub.add_parser('multiplayer').add_argument('capture_folder', type=Path)
    comparison = sub.add_parser("compare")
    comparison.add_argument("first", type=Path)
    comparison.add_argument("second", type=Path)
    worlds = sub.add_parser('compare-worlds')
    worlds.add_argument('first', type=Path)
    worlds.add_argument('second', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'compare-worlds':
            result = compare_worlds(args.first, args.second)
        elif args.action == 'multiplayer':
            result = multiplayer_capture(args.capture_folder)
        else:
            result = failure(args.replay_folder) if args.action == "failure" else compare(args.first, args.second)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Cannot inspect replay: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
