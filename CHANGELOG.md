# Changelog

## 0.5.0

- Gate randomness, dust, pause and fixed-seed changes by both an active recorder scope and the native single-player mode. Multiplayer and idle paths execute the original instruction sequences.
- Gate the simulation observer and halt path as well, so a stale replay cannot freeze multiplayer or suppress its commands.
- Abort an active capture on a multiplayer mode transition without changing the multiplayer pause flag.
- Hide recorder controls from both rendering and input in multiplayer using the native menu's skipped-item behaviour, preserving other extensions' items.
- Add x86 emulation comparisons for original versus gated paths in Crusader and Extreme, including condition flags, stack cleanup and stale halt state.
- Use simulation profile `recorder-sp-v2`; earlier experimental captures require their original module version.

This closes the known unconditional simulation-patch gap. It does not add multiplayer recording or certify multiplayer compatibility. Live multiplayer comparison and full single-player replay/menu tests remain pending.

## 0.4.0

- Replace temporary Skirmish checkboxes with labelled **Record next match** and **Replays** controls.
- Add a paged replay picker using the game's native red frame, text and input handling. Show session status, tick duration and settings compatibility before playback.
- Add **Queue settings restart**: a hidden helper waits for the current game to exit, verifies the executable and saved configuration, and restarts with that configuration. The normal UCP configuration stays unchanged.
- Preselect the requested replay when opening the browser after a queued restart.
- Check native UI entry points separately for Crusader and Extreme; avoid overwriting existing modal IDs or writing past menu arrays.
- Keep rejected preflight checks from freezing a later normal match, while pausing after a failed native playback load.

Validation: 53 tests, including Windows helper tests with process waiting/launching replaced by fakes and emulation of the 32-bit Windows call wrappers; original-binary checks for both games. Native rendering, input handling and the real restart remain **pending live testing**, together with the full replay test from 0.3.0. No game was launched by these automated tests.

## 0.3.0

- Store each recording in its own folder with a starting save, full RNG state, UCP configuration, resolved settings and extension versions.
- Begin recording after Skirmish initialization, keeping lobby commands and randomness out of the replay.
- Validate file hashes, command order, player slots and checkpoint timelines before loading a replay.
- Respect the native command queue's capacity, check inferred payload sizes, and block spectator commands during playback.
- Verify RNG checkpoints and the ending RNG state; stop with a diagnostic on divergence or pending commands.
- Publish completed recordings only after closing and validating their streams. Cancelled or failed captures remain distinguishable.
- Restore temporary save/load dialog state and filenames after errors; never overwrite an earlier recording.

Validation: 36 portable regression tests and native-site checks against Crusader and Extreme. The new starting-save capture and playback path has **not yet passed an end-to-end in-game test**. This is a review/test build, single-player only. Save/load and network commands are unsupported during capture; encountering one marks the capture failed. Replay browsing and settings relaunch follow separately.

## 0.2.0

- Port the existing native hooks and Skirmish controls to the checked Extreme executable.
- Resolve code and data addresses through separate Crusader/Extreme profiles, including Extreme's larger player-state structure.
- Add an optional original-executable verification tool and document the native layout differences.

Validation at this stage: the regression suite passes, both original executables pass address checks, Crusader starts a Skirmish and records player commands, and Extreme reaches its main menu with the module enabled. Complete replay verification and the new session/browser workflow are still under development. Existing recordings must not be shared between variants.

## 0.1.0

- Fix the player-identity detour losing its returned registers and apply the configured fixed seed.
- Correct the dust-effect patch's stack cleanup and replace the complete original instruction.
- Isolate recorder instances, clear prefetched commands/RNG on stop, close files on failed startup, and preserve the local player when stopping.
- Validate replay metadata and command records before starting playback; limit and clear the native payload buffer.
- Compare both RNG values and indices and retain the first divergence instead of silently skipping it.
- Check every native patch location before installation and reject unsupported or conflicting executables. This stage supports the original SHC 1.41 executable only.
- Correct the UCP definition/options schema version to 1.0.0 and add portable LuaJIT regression tests.

This is the repair foundation. Existing recordings are not guaranteed compatible with corrected RNG hooks. The legacy manual lobby setup and playback controls are still present; Extreme, settings snapshots and the replay browser follow separately.
