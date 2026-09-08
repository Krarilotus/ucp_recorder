"""Read-only failure triage and comparison of optional single-player RNG traces."""
import argparse
import hashlib
import json
from pathlib import Path


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
    sequence = commands = checkpoints = gaps = valid_bytes = 0
    segments = 1
    transitions = []
    categories = {}
    footer = None
    last_tick = manifest['startTick']
    next_checkpoint = (last_tick + 63) // 64 * 64
    with (folder / 'commands.jsonl').open('rb') as stream:
        header_line = stream.readline(1024 * 1024)
        header = json.loads(header_line)
        if (header.get('kind') != 'header' or header.get('format') != 5
                or header.get('firstTick') != manifest['startTick']
                or header.get('network') != manifest['initialNetwork']
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
                        next_checkpoint = (tick + 63) // 64 * 64
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
                        checkpoints += 1; next_checkpoint += 64
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
            'issues': issues, 'validPrefixBytes': valid_bytes, 'fileBytes': size,
            'lastJournalTick': last_tick, 'events': sequence, 'commands': commands,
            'checkpoints': checkpoints, 'coverageGaps': gaps, 'timelineSegments': segments, 'commandCategories': categories,
            'transitions': transitions, 'footer': footer,
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
        if entries[0].get("spawnContext"):
            spawns = entry.get("spawns")
            if not isinstance(spawns, list) or len(spawns) > 512:
                raise ValueError(f"{path}: missing or oversized spawn context")
            for spawn in spawns:
                if not isinstance(spawn, dict) or any(type(spawn.get(key)) is not int for key in
                        ("time", "caller", "player", "color", "microX", "microY", "height", "unitType")):
                    raise ValueError(f"{path}: malformed spawn context")
                if not entry["fromTick"] <= spawn["time"] <= entry["time"]:
                    raise ValueError(f"{path}: spawn outside its checkpoint interval")
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
    for a, b in zip(a_rows, b_rows):
        if (a["fromTick"], a["time"]) != (b["fromTick"], b["time"]):
            result.update(status="different checkpoint boundaries", first=a["time"], second=b["time"])
            return result
        result["checkpointsCompared"] += 1
        if (any(a[key] != b[key] for key in ("count", "order", "rng", "calls"))
                or (with_spawns and a["spawns"] != b["spawns"])):
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
    args = parser.parse_args()
    try:
        if args.action == 'multiplayer':
            result = multiplayer_capture(args.capture_folder)
        else:
            result = failure(args.replay_folder) if args.action == "failure" else compare(args.first, args.second)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Cannot inspect replay: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
