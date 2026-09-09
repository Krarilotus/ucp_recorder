# Release and diagnostic builds

Install `recorder-VERSION.zip` for ordinary recording and playback. It keeps
automatic recording, named snapshots, exact settings, integrity checks, native
history/statistics, player portraits and the playback HUD. F3 information is a
viewer feature and stays available in release.

For a targeted investigation, download `recorder-VERSION-diagnostics-bundle.zip`,
extract it, and install the inner `recorder-VERSION.zip` instead. This includes
optional RNG caller/spawn/fire attribution and the offline analysis tools.
Diagnostics are off by default; enable only the requested diagnostic settings.
The common network journal is required for multiplayer recording, despite its
historical `multiplayer-trace.lua` filename, and remains in both builds.

Use one build at a time. The UCP module name/version inside each build is the
same, but its exact package fingerprint differs. Keep the installed artifact
with recordings that need it. Switching artifacts is not a compatibility bypass;
replay still requires its recorded environment. Release ignores optional
diagnostic flags inherited from an old developer preset, without changing that
preset in the caller.

The publisher produces both builds from the same tested commit. Source checkouts
retain diagnostic capability for development. `tools/module_package.py` owns
the packaging rules; it never executes source-tree build scripts.

## Loading work

Binary transfers use an explicit-length copy when the installed CFFI bridge
passes an all-byte probe. Older bridges retain a verified fallback. Multiplayer
tick preflight validates packed clocks and RNG indices in bounded chunks, without
creating playback tables for every tick. Playback still decodes and validates
the commands/states it actually consumes.

Prepared native starting saves are cached by captured world identity, converter
revision and executable. Every reuse verifies the source sections and prepared
file digest. Missing, damaged or older derived caches are rebuilt; damaged
original recordings are rejected. Conversion still round-trips the original
native compressor, and files are published only after complete writes.

These changes reduce unnecessary work; they do not promise a 100 ms cold load.
Measure recorder startup, replay preparation, and the native world-load phase
separately, on the same recording and environment.

The design keeps the original initial-state/input approach. Factorio documents
why deterministic save/load is required for replay and resumed multiplayer:
https://www.factorio.com/blog/post/fff-270 . OpenRA's ReplayConnection also shows
that replay network processing has its own scheduling/consumption boundary:
https://github.com/OpenRA/OpenRA/blob/bleed/OpenRA.Game/Network/ReplayConnection.cs .
Neither establishes a transferable SHC startup-time guarantee. Reusing validated
derived data and eliminating copies are local optimizations, not a reason to
skip configuration or simulation integrity checks.
