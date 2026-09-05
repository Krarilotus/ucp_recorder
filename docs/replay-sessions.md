# Replay sessions (0.3.0)

This stage replaces manual recreation of the lobby with a native starting save and full RNG snapshot. It is ready for code review and isolated testing, not yet confirmed for complete live playback.

## Files

Each session reserves `ucp/replays/YYYYMMDD-HHMMSS-NNNN/`. Its manifest records the game variant, expected executable identity, simulation patch profile, active UCP settings, resolved configuration and extension versions. The folder contains:

- `start.sav`: native save captured after Skirmish initialization.
- `rng.bin`: the complete 40,016-byte RNG structure, including its table.
- `ucp-config.yml` and `environment.json`: startup settings and resolved environment.
- `stream-commands.json`, `stream-rng-sync.json`, `stream-infself.json`: commands, 64-tick RNG checkpoints and initial match information.
- `manifest.json`: status, timeline, command count, final RNG values/indices and SHA-256 hashes.

The manifest moves through armed, recording and complete. Cancelled and failed sessions cannot play. Stream close failures and validation failures prevent completion. Metadata is replaced through a temporary file; this prevents a partial JSON document becoming the published manifest, but does not promise recovery from every power-loss scenario.

## Simulation boundary

Capture starts after the native Skirmish launch function initializes the game. Checkpoints observe the same point immediately before each simulation tick, independent of render-frame count. The ending state is the last observed boundary, not the later time at which an exit dialog runs. Future commands still queued when recording ends are excluded from the finalized stream.

Playback preflights all files, loads the native starting save, restores the full RNG structure, and checks the loaded tick and local player. The native scheduler receives recorded commands with their recorded execution tick. It must have a free slot; its inferred payload length must match the recorded length. At completion, all recorded commands must have been scheduled and observed returning from their native handlers. Ownership, dispatch order, actor, tick, category and payload are checked before execution. RNG verification covers two values and two indices, **not a full world-state checksum**.

The local single-player identity stays intact. New commands queued by a spectator are blocked while playback is active, finished or failed. This hook may also block commands from automation extensions; compatibility with those extensions requires separate analysis and testing.

## Configuration compatibility

Settings are captured when the module enables, not reread when the user begins a recording. Playback requires the captured configuration bytes and the resolved configuration/extension-version environment to match. A restart with the saved configuration is necessary when these differ. This stage does not relaunch automatically.

Version equality does not prove that unpacked extensions have identical source files, or that map assets and external resources are unchanged. No extension download, installation or version switching is performed. Replays are local test artifacts; native save/payload handling has not been audited as a parser for hostile downloaded files.

## Unsupported cases

Multiplayer capture/playback, resynchronization packets, lobby commands, native save/load commands, unknown extension commands (except the explicit Automarket 1.1.0 adapter) and cross-variant playback are excluded. Unsupported commands during recording fail the capture with an error instead of silently omitting actions. Game speed and pause behaviour, automated actions, native save/load RNG side effects, repeated playback, match-end transitions and Extreme matches still require live verification.

## Native evidence

`engine-sites.lua` contains checked entry bytes for both executables. Save/load uses FilePackager and the game's load-dialog handler, with a temporary filename override limited to save resources. Temporary resource type, filename, progress callback and list-selection fields are restored after failure. The scheduler copy guard replaces the six-byte load of `commandSize` before the payload copy. The simulation hook runs before the native RNG advance and tick increment; its halt branch skips that tick sequence.

See `tests/check_executables.py` for read-only checks against original executable files and `tests/test_engine.py` for injected native-wrapper failures. Neither replaces a successful live capture/load/replay comparison.
