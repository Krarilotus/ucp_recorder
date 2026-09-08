# Focused single-player RNG diagnosis

An RNG divergence is a failed replay, not a normal pause or successful ending.
The checkpoint reports where the difference was detected. It cannot establish
when the underlying world state first differed or which action caused it.

## If you already have a failed recording

1. Keep its entire folder under `ucp/replays/`, including `desync.json` and
   `last-playback.json`. Copy the folder before repeating playback: those two
   reports describe the latest attempt and are replaced by later failures.
2. Replay the same recording at normal speed with minimal interaction. Leave
   the failure message open. Compare its tick with the first attempt. A repeat
   at the same tick supports reproducibility; it does not prove the cause.
3. Do not edit the recorded configuration or RNG state to get past the check.
   Playback must use the recorded versions and options.

With Python 3 installed, the included read-only tool summarizes the failure,
the previous checkpoint, and nearby commands:

```
python tools/inspect_replay.py failure "path/to/ucp/replays/REPLAY_ID"
```

The index delta is reported modulo 20,000. It is not an exact count of calls:
additional complete wraps cannot be inferred from two index values alone.

## A new recording with caller evidence

1. Enable **Single-player RNG diagnostics** in the recorder's UCP options
   before launching the game. Leave the rest of the test setup unchanged.
2. Make a fresh single-player Skirmish recording. For the current regression,
   retain Ascension/Automarket and allow AI combat; save a named copy if useful,
   then finish through **Quit Mission** to preserve the full recording.
3. Replay the full recording with the same settings. Stop after the first
   mismatch; there is no need to play a full new match after every failure.
4. Share the whole recording folder. Separate files are stored under
   `rng-attribution/record-.../calls.jsonl` and
   `rng-attribution/play-.../calls.jsonl`. Repeated attempts get unique folders.

Compare two matching attempts with:

```
python tools/inspect_replay.py compare "record-.../calls.jsonl" "play-.../calls.jsonl"
```

The tool identifies the first differing checkpoint interval and its differing
native return addresses, counts, and first/last call ticks. Return addresses
identify the instruction after a call, not necessarily a function's entry.
An unchanged count with a different ordering checksum is also useful evidence.
The checksum is diagnostic and may collide; matching traces do not prove an
equal world or a completed replay. Missing end markers and unmatched tails are
reported explicitly. The original replay RNG/resource checks remain authoritative
for their respective domains.

Named replay copies retain the gameplay streams but do not copy this optional
diagnostic tree. Use the full source recording when comparing capture to playback.

## Implementation and limits

The existing RNG entry observers preserve the native registers and execute the
original RNG instructions. A single shared observer routes single-player and
multiplayer events to their respective collectors. Single-player collection
starts after the initial snapshot/RNG restoration and ends on completion,
failure, or leaving the session. It flushes before checkpoint validation, so
the first detected failing interval is preserved.

Each interval holds at most 512 distinct `(stream, native return address)`
entries. Calls update counts and a rolling 32-bit ordering checksum in memory;
there is no per-call file write. Output is capped
at 64 MiB per attempt. A limit or I/O error closes the diagnostic file and logs
`RNG attribution stopped`; it never pauses the game or changes RNG state. Such
a trace can lack its end marker and is incomplete. Diagnostics add CPU/storage
overhead and are disabled by default.

From 0.34.0, an interval can also contain up to 512 unit-spawn context records.
These identify the tick, caller, player, display color, microtile position,
height and unit type at `spawnUnit`'s RNG2 call. They reuse the existing RNG
observer; no spawn hook or gameplay write is added. Native stack-layout tests
cover both supported executables. If another module replaces the checked spawn
entry or RNG call, the header reports `spawnContext: false` and ordinary caller
attribution remains available. Old traces remain readable. The comparator only
compares spawn context when both headers explicitly report it as available.

The read is at SHC return `0x0053E5CB` / Extreme `0x0053E9EB`. The original
spawn function has saved ESI, EBP, EDI and EBX before calling RNG2; from the RNG
entry stack, offset 20 is its caller and offsets 24 through 44 are its six
arguments. Context is observed before the native RNG call executes.

The option is part of recorded UCP settings. An old recording cannot acquire
its missing original caller history retroactively. Version 0.30.0 keeps
simulation profile `recorder-sp-v10`; this is observation, not a randomness fix.

## Current regression

On recorder 0.29.0 with Ascension 1.0.11 and Automarket 1.1.0, the full SHC
recording `20260906-211836-0001` sealed normally at tick 224,023 with 2,310
commands. Its maximum-speed playback failed at checkpoint 22,912 after 311
scheduled commands. The preceding checkpoint at 22,848 passed the existing
RNG table and resource checks. There are no recorded commands in that interval.

| State | RNG1 value | RNG2 value | RNG2 index | RNG1 index |
| --- | ---: | ---: | ---: | ---: |
| Expected | 1051 | 8648 | 17170 | 4038 |
| Playback | 1051 | 11850 | 17165 | 4038 |

Native SHC `0x0046A7D0` increments RNG2's index and wraps at 20,000; the observed
difference is consistent with five fewer advances in playback. This differs
from the earlier church-panel RNG1 mismatch. It does not establish that speed,
Automarket, or a particular command is responsible.

Read-only OpenSHC/Ghidra inspection confirms RNG2 is also consumed by projectile
creation (`0x00404AE0`), poison-cloud updates (`0x004087C0`), heads-on-spikes
updates (`0x00405C00`), and crow creation (`0x004F3150`). These are investigation
targets, not identified defects. Suppressing them indiscriminately would change
gameplay or entity state. Use caller evidence before selecting a fix.

### Restricted loader correction (0.30.1 / 0.31.1)

The initial collector required a host `bit` module, which UCP cannot resolve
inside an extension ZIP. The corrected collector has no external bit-library
dependency. Format 2 identifies its arithmetic ordering checksum; the comparator
accepts both formats separately but rejects comparisons across formats.

### Reproduced with caller traces (0.33.1)

SHC recording `20260908-132338-0001`, Ascension 1.0.11 / Automarket 1.1.0,
human versus Wolf on Der grüne Punkt, finalized naturally at tick 90,505. Two
playback attempts failed at 18,112 before either of its two player commands
was scheduled. One attempt opened replay controls and selected player 2; an
untouched repeat produced the same failure. The recording itself included a
pause/options visit. This rules out playback menu interaction as a necessary
trigger for this reproduction; it does not yet isolate recording-time effects.

Caller counts, ordering checksums and RNG states agree through 18,048. At
18,106, recording has one additional RNG2 call at each of `0x0052EFDC`,
`0x0052EFFE` (unit name assignment) and `0x0053E5CB` (unit spawning). At the
next checkpoint, expected RNG is `[2494,22591,1875,18179]`, playback is
`[2494,13729,1872,18179]`. The trace directly establishes three fewer calls,
not just a modulo-index difference. The missing unit and the earlier world
state that caused it remain unknown; the new spawn context targets that gap.
Do not suppress these RNG calls: they participate in real unit creation.
