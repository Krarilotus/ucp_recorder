# Persistent multiplayer capture: stage one

Version 0.36.0 removes the short diagnostic window from ordinary multiplayer
capture. With automatic recording enabled (the default), each participating PC
opens its own `ucp/multiplayer-recordings/TIMESTAMP-NNNN` folder at its first
native simulation callback. Loading/lobby callbacks cannot start the capture.
Normal mission exit seals the journal; named copies do not stop it.

**This stage does not produce playable multiplayer replays.** It establishes the
durable source data needed for later stages. Captures stay outside the playable
single-player library and always declare `playable: false`.

## Saving and collecting

- Capture starts and saves on both host and client without a separate button.
- **Pause > Replay status** shows progress and **Save capture as...**. The native
  name dialog creates a separately named byte-exact snapshot of the flushed
  journal. It does not call the game's save routine or modify the source stream.
- Keep the entire capture folder, including `capture.json`, `commands.jsonl`,
  `initial-rng.bin`, `environment.json`, `ucp-config.yml` and `replay-config.yml`.
  Version 0.37.0 also adds `world.json`, `world-layout.bin`, `world.bin` and,
  with Automarket enabled, `automarket.bin`; keep those with the capture too.
- `multiplayerDiagnostics` adds per-caller RNG attribution. Without it, captures
  retain command/checkpoint/resource/RNG and native world-hash observations with
  no extra hook on each RNG call. Diagnostic start/end options apply only when
  automatic recording is disabled and diagnostic-only mode is selected.
- Each journal stops explicitly at 256 MiB. Synchronous flushing has overhead;
  this release does not claim measured performance for full-match capture.

The journal retains the format-5 observation schema for existing comparisons.
`capture.json` uses an independent versioned persistence schema. `closed` means
the writer committed its ending, not that command coverage is complete. Names
are metadata, never paths. On-disk binary mode avoids Windows newline conversion
changing the snapshot byte offsets. Copies use bounded 64 KiB buffers.

## Failure and network transitions

All command/RNG/network observers remain read-only with respect to the game.
An error closes capture, reports the problem, and preserves existing files; it
does not pause multiplayer or replace a command category. Previously flushed
data remains useful after a crash, but Lua flush is not a guarantee against
hardware/power loss. No missing ending is silently fabricated.

Roster changes, native synchronization phases and DirectPlay messages remain
unsupported playback events. They are retained rather than stopping persistence.
A native tick rewind starts an explicitly marked timeline segment; it does not
assert that the resynchronized world has been serialized. Existing strict
comparison remains incomplete across these transitions.

```text
python tools/inspect_replay.py multiplayer PATH_TO_CAPTURE_FOLDER
python tools/compare_multiplayer.py HOST/commands.jsonl CLIENT/commands.jsonl --inspect
```

The first command checks sidecar hashes, sequence/count boundaries and intact
newline-delimited journal prefixes. It reports interrupted tails without editing
any source files. This is framing/integrity inspection, not full command-schema
validation. The existing strict comparator provides its own separate checks.
An unsealed prefix can come from an active capture or a crashed process.

## Gates before the next user test

1. **Persistence:** automated host/client, named-copy, disk-failure, interrupted
   row, identity/sync transition and tick-rewind tests. No game session required.
2. **Starting world:** audit the native multiplayer save path and extension save
   wrappers, capture a restorable start at a defined command boundary, and prove
   that saving does not change either peer's simulated state.
   [0.37.0 captures and verifies read-only world evidence](multiplayer-world-state.md);
   native restore and complete extension coverage remain open.
3. **Offline playback:** restore human/AI identities without a live transport;
   dispatch the recorded native commands; classify/reproduce immediate and
   system events; restore extension state with the recorded UCP configuration.
4. **Focused two-PC test:** a short predetermined command sequence, save on both
   peers, end normally and replay each file offline. Collect first divergence,
   source commands, RNG/resource and native world-hash evidence automatically.
5. **Recovery:** controlled disconnect/resynchronization with explicit segment
   boundaries and saved replacement world states. Verify both surviving files.

Only then broaden to long AI/Automarket/Ascension games. The 0.35.0 physical
baseline matched 1479 timed commands, 2033 resource checkpoints, RNG2 state and
650 native world-hash observations, but was bounded at tick 131072 and returned
incomplete for immediate traffic. It does not validate this new persistence
stage or any offline multiplayer playback.
