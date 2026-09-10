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
  can save the actual ending boundary. Release verification happens every 1,024
  ticks; diagnostic builds retain detailed 64-tick observations.
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

## 0.49.0: keep inputs, reduce evidence

The verification profile is recorded in the manifest, independently of the
simulation profile. `state-digest-v1` stores the tick, four RNG counters, and one
SHA-256 of the fixed native RNG block followed by all eight resource blocks.
The absent profile means the existing detailed 64-tick format; older recordings
are still read without rewriting them. Unknown profiles and missing checkpoints
are rejected before native loading. Release fingerprints can detect a mismatch
later (up to the next 1,024-tick boundary) and cannot identify an individual
resource; diagnostic builds retain that detail. These checks sample RNG/resources,
not the entire simulation state, and do not prove all game state is identical.

Recorded resources stay as 800 native bytes at each observed tick. Capture decodes
the 200 integers only for the initial/final manifest or detailed diagnostics.
Multiplayer command records omit resource snapshots in Release; executed payloads,
before/after RNG inputs, every native tick boundary and recovery records remain.
SHA-256 of RNG data uses the existing native hashing service, not the framework's
Lua SHA implementation. Preparation yields when its time budget expires, rather
than imposing a fixed quota of progress notifications per menu frame.

An offline benchmark used the 1,865,453-tick match's original command/maintenance
streams and the real UCP Lua 5.4 JSON parser. Sparse rows used its original times
and counters with placeholder fixed-length digests: this is a performance fixture,
not a converted playable replay. Across three runs, median stream preflight work
fell from 7,611 ms to 67 ms. Verification data fell from 16,516,612 bytes / 29,147
rows to 228,798 bytes / 1,821 rows (98.6% fewer bytes). The OS hashing boundary was
modeled with hashlib; these numbers exclude settings/asset verification, native
world loading, disk-cache variation and game simulation. Existing recordings keep
their detailed data and do not receive this size reduction automatically.

No replacement binary checkpoint format, extra runtime dependency or new game
simulation path was needed. The native world reload and asset scan still need
separate measurement; a 100 ms complete replay start is not established.

## 0.49.3 load review

A Windows measurement with the shipped Lua 5.4/RPS runtime and production native
SHA-256 measured these medians over three runs:

| Isolated operation | Time |
| --- | ---: |
| Hash three settings metadata buffers in Lua / native | 48.90 / 12.26 ms |
| Hash the starting RNG buffer in Lua / native | 8.73 / 2.57 ms |
| Hash 644 configured files (303,744,585 bytes) natively | 373.25 ms |
| Preflight the older detailed 1,865,453-tick recording | 8,121.79 ms |
| Preflight the synthetic sparse equivalent | 92.12 ms |

Lua and native metadata/RNG hashes matched exactly. The physical-file benchmark
uses CRT reads instead of UCP's virtual-file opener; cache state was uncontrolled.
The sparse fixture contains placeholder digests and is not playable. These are
operation measurements, not end-to-end replay loading or simulation timings.
Older detailed recordings retain their larger validation cost.

The installed 0.49.2 test configuration spent 1,734 ms CPU in Recorder startup,
including 1,547 ms capturing recorded settings (about 1,749 ms wall time from
module enable to its startup report). A sub-100-ms startup overhead is therefore
not established. Native metadata hashing reduces one measured cost; it does not
eliminate directory enumeration, asset hashing or native world restoration.

The live save-load test exposed a separate correctness defect: at completion of
the native load handler, currentView (+0xc) still held 41, the load dialog. Native
switchMenu writes requestedView (+0x18); the presentation loop commits it later.
Recording admission now checks requestedView 14, the loaded skirmish type and
singleplayer mode after a successful reader completion. The starting snapshot
still waits for the first simulation boundary. No menu-loop or simulation patch
is needed for this correction.

## Progress-only hashing and playback display (0.49.4)

Asset verification and save/container progress callbacks now receive byte counts
directly. Native hashing no longer copies each 64 KiB input buffer into a Lua
string just to report progress. Byte-parsing consumers retain their existing
callback; hash, size-limit and cancellation checks remain in both paths.

An offline comparison using the shipped 32-bit RPS runtime hashed 644 assets
(303,744,585 bytes), with 5,004 progress callbacks. Median times over three runs
were 380.27 ms with byte copies and 361.25 ms with count-only callbacks. These
physical-file, warm/uncontrolled timings are not a game VFS load benchmark. The
direct improvement is avoiding about 304 MB of temporary Lua payload copies.

The live 0.49.3 loaded-save replay completed with matching verification, but
preparation took 2,188 ms. Its small stream scan took about 1.8 ms in a separate
offline test. Asset enumeration/VFS work and the native recording-start snapshot
remain profiling targets; this change does not establish sub-100-ms loading.

The display-only HUD bar shares the existing overlay renderer, native Pencil
fill and loading-bar palette. Its progress value and tick label are sampled at
250 ms intervals, with immediate refresh on completion or session replacement.
Drawing remains part of normal frame rendering so camera redraws cannot erase
the bar. It adds no simulation callback, replay data or per-tick allocation.

## Platform status

The 0.49.2 presentation review removed 35 unused labels from each of ten catalogs
(about 21 KB of source text). Catalogs now load only for the selected language;
English loads none. A recognized TextManager marker bypasses the fallback language
provider. HUD shadow and lettering share one encoding/measurement pass. Tests
check these call counts and lazy loading; this is not a whole-game speed benchmark.
Recording inputs, verification, recovery state, asset checks and native restoration
were retained because the current replay path requires them.

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
