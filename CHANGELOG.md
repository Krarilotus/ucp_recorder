# Changelog

## 0.3.0

- Store each recording in its own folder with a starting save, full RNG state, UCP configuration, resolved settings and extension versions.
- Begin recording after Skirmish initialization, keeping lobby commands and randomness out of the replay.
- Validate file hashes, command order, player slots and checkpoint timelines before loading a replay.
- Respect the native command queue's capacity, check inferred payload sizes, and block spectator commands during playback.
- Verify RNG checkpoints and the ending RNG state; stop with a diagnostic on divergence or pending commands.
- Publish completed recordings only after closing and validating their streams. Cancelled or failed captures remain distinguishable.
- Restore temporary save/load dialog state and filenames after errors; never overwrite an earlier recording.

Validation: 34 portable regression tests and native-site checks against Crusader and Extreme. The new starting-save capture and playback path has **not yet passed an end-to-end in-game test**. This is a review/test build, single-player only. Save/load and network commands are unsupported during capture; encountering one marks the capture failed. Replay browsing and settings relaunch follow separately.

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
