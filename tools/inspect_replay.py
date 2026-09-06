"""Read-only failure triage and comparison of optional single-player RNG traces."""
import argparse
import json
from pathlib import Path


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
    if not entries or entries[0].get("kind") != "header" or entries[0].get("format") != 1:
        raise ValueError(f"{path}: unsupported or missing attribution header")
    checkpoints = [e for e in entries if e.get("kind") == "checkpoint"]
    previous = entries[0]["firstTick"]
    for entry in checkpoints:
        if entry["fromTick"] != previous or entry["time"] < previous:
            raise ValueError(f"{path}: non-contiguous attribution checkpoints")
        keys = [(c["stream"], c["returnAddress"]) for c in entry["calls"]]
        if len(set(keys)) != len(keys) or sum(c["count"] for c in entry["calls"]) != entry["count"]:
            raise ValueError(f"{path}: inconsistent attribution counts")
        previous = entry["time"]
    return entries[0], checkpoints, entries[-1].get("kind") == "end"


def compare(first, second):
    a_header, a_rows, a_complete = trace(first)
    b_header, b_rows, b_complete = trace(second)
    for key in ("replay", "variant", "executable", "firstTick", "rng"):
        if a_header[key] != b_header[key]:
            raise ValueError(f"Attribution starting {key} differs")
    result = {"firstClosed": a_complete, "secondClosed": b_complete,
              "status": "matching observed prefix", "checkpointsCompared": 0,
              "caution": "Caller counts and the ordering checksum do not prove equal world state."}
    for a, b in zip(a_rows, b_rows):
        if (a["fromTick"], a["time"]) != (b["fromTick"], b["time"]):
            result.update(status="different checkpoint boundaries", first=a["time"], second=b["time"])
            return result
        result["checkpointsCompared"] += 1
        if any(a[key] != b[key] for key in ("count", "order", "rng", "calls")):
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
            return result
    result["unpairedCheckpoints"] = abs(len(a_rows) - len(b_rows))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("failure").add_argument("replay_folder", type=Path)
    comparison = sub.add_parser("compare")
    comparison.add_argument("first", type=Path)
    comparison.add_argument("second", type=Path)
    args = parser.parse_args()
    try:
        result = failure(args.replay_folder) if args.action == "failure" else compare(args.first, args.second)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Cannot inspect replay: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
