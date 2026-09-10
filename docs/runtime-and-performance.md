# Runtime ownership and performance

The game simulates the replay. Recorder restores a starting world through the
extension-aware native save reader and submits recorded input to the original
command scheduler. AI, movement, pathfinding and combat remain native game work.
Recorder owns command timing, restoration of recorded state, viewer controls and
verification; it does not implement a second game simulation.

## Cost boundaries

- Loading verifies persisted input and configured assets before native loading.
  Command playback streams one pending command; preparation still scans the input
  to reject malformed records before they reach native handlers.
- The native load preparation builds caches but also resets saved simulation
  values. Recorder currently reapplies the world with the same native reader after
  preparation. Removing that read requires preserving those values at their owning
  boundary; simply skipping it would reintroduce restoration differences.
- Recording retains the latest RNG and resource state so a quit/results transition
  can save the actual ending boundary. Checkpoint hashing happens every 64 ticks;
  optional detailed RNG attribution is omitted from release builds.
- Settings restart is separate from loading a replay with already matching
  settings. Its helper is not invoked by the simulation tick loop.

In 0.48.7, resource snapshots avoid eight intermediate byte tables per sample.
Lua 5.4 uses its built-in signed integer decoder; LuaJIT uses equivalent scalar
byte decoding. Initial RNG hashing uses the bytes just written, and checkpoint
records reuse the current tick's RNG counters. None of these changes alter the
replay format, native simulation or integrity checks.

A local decoder-only comparison with modeled memory reads (five samples of
10,000 snapshots) improved median time from 161 to 145 ms on Lua 5.4 and from
36 to 14 ms on LuaJIT. This is not a game benchmark: it cannot establish total
recorder overhead, startup latency or Wine/Proton performance. Whole-game claims
require matched scenarios and separate measurements of preparation, native load,
and simulation throughput.

## Platform status

Runtime logic is Lua with native game/UCP and Windows APIs. Python is used only
for developer tests, preview packaging and optional offline inspection tools.
The release runtime requires no Python installation.

Linux CI checks portable logic; it does not run the game. Original SHC and UCP
are Windows software, so Linux gameplay requires Wine/Proton acceptance. The
current settings-restart helper invokes Windows PowerShell and is a known
portability gap. A compiled replacement must preserve the original process's
launch environment, validate the recorded configuration, survive that process
exiting, and leave normal user settings untouched. There is no need to add a
restart hook to each simulation tick.
