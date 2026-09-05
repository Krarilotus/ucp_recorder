# Changelog

## 0.12.0

- Fix the lobby crash caused by Lua filename hooks clobbering registers used by native callers. Use native filename overrides only while loading the replay's starting save.
- Fix the first-tick crash by moving the pause guard away from an incoming branch target, preserving the original unpaused entry path.
- Bootstrap Windows file operations from loaded system exports, including named forwarders, and compile the stdcall bridge through the supported UCP assembly API.
- Terminate native path/text buffers explicitly, use the initialized game font with a shadow, and place Record/Replays in gaps between existing Skirmish controls.
- Capture the starting save at the first simulation boundary following match initialization.
- Guard all seven mood-selection calls that advance simulation RNG, in addition to the previous music guards, for Crusader and Extreme. Music keeps using the current RNG value; this can change track variety. These changes apply only during single-player recorder sessions; idle and multiplayer paths retain native behavior.
- Use simulation profile `recorder-sp-v6`; older captures require their original module version.

Validation: 104 automated tests and original-executable checks for both variants, including complete mood-function RNG-call coverage. Live Crusader tests verified recording, browser selection and starting-save loading, and exposed RNG drift traced to music selection. The final music fix has not yet been retested in game. Complete playback, player commands, Extreme, settings restart and multiplayer still need live validation; multiplayer replay remains disabled. See [live evidence](docs/live-validation.md).

## 0.11.0

- Compare SHA-256 of the complete 40,016-byte RNG structure after restoring the starting save, at periodic checkpoints and at the ending boundary. Detect different stored random arrays even when current RNG values and indices match.
- Retain the last observed RNG bytes for completion, so leaving the match cannot change the state being certified. Hash at checkpoints/completion, while copying the current RNG bytes at each recorded tick.
- Add full RNG hashes to periodic multiplayer diagnostics and compare resolved UCP configuration, framework and extension order/versions before comparing peers. Missing or incompatible evidence is rejected.
- Use single-player profile `recorder-sp-v5` and multiplayer trace format 3. Older recordings need their original module version; the comparator still accepts paired older trace formats with their original evidence limits.

Validation: 98 automated tests, including altered RNG array bytes with unchanged current values/indices, final-state preservation, missing evidence and observer failure isolation. Full-world state and live multiplayer/replay validation remain outstanding; multiplayer replay is not enabled.

## 0.10.0

- Add periodic multiplayer RNG/resource evidence before native simulation advancement, including periods with no player commands.
- Keep the optional observer independent of the single-player replay halt/patch scope; preserve native registers, flags, stack and tick continuation.
- Deduplicate paused boundaries and compare format-2 command/checkpoint streams, rejecting missing periodic evidence. The comparator still accepts paired format-1 traces.

Validation: 91 automated tests, including x86 emulation for both variants with a stale halt flag and register-clobbering diagnostic callbacks. Live multiplayer timing and trace comparisons remain pending; multiplayer replay is not enabled.

## 0.9.0

- Add opt-in multiplayer command diagnostics, disabled by default. Observe the resolved actor, payload, scheduled/executed tick and post-command RNG/resource state without injecting, suppressing or pausing multiplayer commands.
- Isolate logging failures from native dispatch, and mark untracked or interrupted captures incomplete.
- Include a standalone trace comparator that reports the first difference between two peers and rejects incomplete evidence.
- Clarify that a fixed starting seed alone does not guarantee deterministic gameplay.

Validation: 87 automated tests, including native callback pass-through on logging failure and peer trace comparison. This is multiplayer diagnostic support, not multiplayer replay; live multiplayer traces are still needed.

## 0.8.0

- Verify all 25 native resource slots for each of the eight players when loading the starting save, at periodic checkpoints and at the ending boundary.
- Detect wrong gold/stockpile totals even when commands and RNG values still match; report the first differing player, resource, expected amount and actual amount.
- Validate resource evidence before loading a replay, and preserve it in the completion report.
- Use simulation profile `recorder-sp-v4`; earlier experimental captures require their original version.

Validation: 79 automated tests and native operand checks for Crusader and Extreme. This adds resource-state verification, not a complete world-state checksum or multiplayer playback. Live replay tests remain pending.

## 0.7.0

- Add an explicit Automarket 1.1.0 adapter for settings commits through protocol 1.0.0. Validate the registered protocol number, payload size, owning player, fee and Boolean fields. Unknown custom protocols remain excluded.
- Stage replay parameters in protocol's native receive buffer and restore that buffer after success or failure.
- Preserve Map Extensions 1.0.0's save wrapper so the starting save follows its custom-state serialization path. Require recorder to load after protocol before modifying dispatch code.
- Include the Automarket adapter and protocol registration in replay compatibility checks. Weekly automatic trades continue through the simulation without duplicate replay injection.

Validation: 74 automated tests, Lua syntax checks and original-executable checks for both variants. The adapter, custom save restoration and actual automated trades still require live testing; this is not a multiplayer replay release.

## 0.6.0

- Capture timed commands when their native handlers return, including inputs delivered directly to the received-command scheduler. Record their actual execution tick and resolved actor.
- Verify playback command ownership, order, actor, tick, category and payload before dispatch, and count execution only after the handler returns. Suppress a mismatching dispatch and subsequent commands in the stopped batch.
- Keep pending replay commands owned until execution is observed, even if native code changes their slot state.
- Preserve the protocol dispatch hook and original multiplayer dispatch behaviour.
- Use simulation profile `recorder-sp-v3`; older experimental captures require their original version.

Validation: 68 automated tests and original executable checks for Crusader and Extreme. Full live replay and custom extension protocol support remain pending.

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
