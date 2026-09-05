# Changelog

## 0.1.0

- Fix the player-identity detour losing its returned registers and apply the configured fixed seed.
- Correct the dust-effect patch's stack cleanup and replace the complete original instruction.
- Isolate recorder instances, clear prefetched commands/RNG on stop, close files on failed startup, and preserve the local player when stopping.
- Validate replay metadata and command records before starting playback; limit and clear the native payload buffer.
- Compare both RNG values and indices and retain the first divergence instead of silently skipping it.
- Check every native patch location before installation and reject unsupported or conflicting executables. This stage supports the original SHC 1.41 executable only.
- Correct the UCP definition/options schema version to 1.0.0 and add portable LuaJIT regression tests.

This is the repair foundation. Existing recordings are not guaranteed compatible with corrected RNG hooks. The legacy manual lobby setup and playback controls are still present; Extreme, settings snapshots and the replay browser follow separately.
