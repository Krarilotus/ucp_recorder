# Changelog

## 0.29.0

- Support ten omitted native gameplay commands on Crusader and Extreme: change
  workshop production, operate drawbridges, select siege engines and their units,
  release dogs, remove tower siege equipment, delete wall/pitch areas, request
  unit-linkage recalculation, replenish ammunition and place braziers.
- Audit all 120 native command-table entries and document admitted commands and
  deliberate exclusions. Retain exclusions for save/load, lobby, immediate,
  network/resync and player-connection operations instead of accepting every
  command with a timed payload.
- Verify every native receive handler's payload size and timestamp policy on
  both variants, and test the production handler and its real UID-checked action.
  Add capture/playback and malformed-layout tests for the new commands.
- Keep simulation profile `recorder-sp-v10` and the 0.28.0 recovery behavior:
  capture failure pauses once and releases normal gameplay after unpause.

## 0.28.0

- Record and replay native rally-point commands, including cathedral/monk,
  barracks, mercenary and guild assembly points, on Crusader and Extreme.
  Validate their five-byte timed payload instead of stopping capture.
- Stop a failed recording without disabling normal single-player controls.
  Pause once, mark the capture failed and detach recording hooks from dispatch;
  the live command still executes and ordinary unpause resumes the match.
  Failed playback continues to block recorded commands and simulation.
- Label the pause-menu entry `Replay failed - details` after an error and explain
  whether the player can resume an unrecorded match or must leave failed playback.
- Keep simulation profile `recorder-sp-v10`, including the church wedding RNG fix
  from 0.27.0. Add regression tests for rally-point layouts, resumed command
  dispatch, failed-capture lifecycle and the failure status menu.

## 0.27.0

- Prevent the chapel, church and cathedral wedding announcement from advancing
  simulation RNG during single-player recording or playback. Keep the native
  panel and eligible-couple selection available; presentation choices reuse the
  current random value. Idle games and multiplayer keep their original behavior.
- Advance the single-player simulation profile to `recorder-sp-v10`. Record a
  fresh match to test this fix. Older captures still require their original
  package; this cannot reconstruct unrecorded menu visits in an existing replay.
- Add original-executable tests on Crusader and Extreme for wedding selection,
  empty candidate lists, repeat visits, candidate limits, RNG wrap, read-only
  unit data and unchanged idle/multiplayer behavior.
- Track replay-only player viewing, usable inspection controls, failed-playback
  feedback, native menu polish and offline multiplayer playback in the roadmap.

## 0.26.0

- Check Automarket compatibility and every enabled multiplayer diagnostic hook
  family before installing recorder hooks. Keep the strict byte guards.
- Write `ucp/recorder-startup.txt` with loaded extension versions/order, check
  stages and the original failure. Also print it to the console/log. Reporting
  failures cannot mask a launch error; configuration option values are not dumped.
- Include addresses and expected/found bytes in session, UI, simulation and
  diagnostic hook conflicts. Missing bytes remain failures.
- Add a fresh-machine setup guide, PR-release download location, Ascension
  dependency/order guidance, first replay check and troubleshooting for the
  tester's 0.17.0 save conflict. That CALL-wrapper fix already shipped in 0.18.0.
- Test both variants' save wrappers and strict tail/version rejection, report
  failures and diagnostic preflight ordering. Multiplayer playback is unavailable.

## 0.25.0

- Save a separate replay launch configuration with the exact loaded extension
  versions, order and resolved options. Restarts use this pinned profile instead
  of resolving the original configuration's version ranges again. Preserve the
  original UCP configuration alongside it.
- Compare new recordings using their effective recorded environment: formatting,
  comments or version-range text alone no longer force a restart when the loaded
  options, extension versions/order and framework already match.
- Preserve literal nested option data through UCP's contents.value normalization.
  Round-trip the profile through the installed YAML bridge before capture and
  reject values it would silently coerce or truncate.
- Reject nonfinite option values with their configuration path before JSON can
  silently discard them.
- Carry the launch profile and its checksum into named copies, validate it before
  playback, and recheck original settings, launch settings and environment after
  the helper has waited for the game to close. A failed restore cannot cause an
  endless restart loop; legacy recordings retain their original restart path.
- Add tests using the production UCP YAML parser, JSON encoder, version matcher
  and option normalizer, plus file-integrity, menu and Windows-helper coverage.
  No content/asset fingerprinting or multiplayer playback is added by this change.

## 0.24.0

- Capture all 14 native world-hash subtotals immediately after calculation on
  Crusader and Extreme. The game's 48-byte player stride overlaps two values;
  delayed reads can report overwritten data. Observation copies values without
  changing native hashes, synchronization, commands or simulation state.
- Add `worldHashes` to multiplayer comparison `--inspect`: pair completed
  calculations by advertised match tick, report the first differing domains,
  preserve total-hash collisions, and count unmatched samples and duplicates.
  Reject conflicting samples, invalid sums, incomplete windows and peer changes.
- Bound pending samples and expose unflushed end-of-match observations. Read or
  storage failures stop diagnostics without suppressing native gameplay.
- Add original-executable observer checks for all eight slots and native skip
  paths on both variants, plus Lua capture and malformed comparison fixtures.
  This does not enable multiplayer playback or establish the cause of the prior
  RNG1 difference. Single-player simulation profile remains `recorder-sp-v9`.

## 0.23.0

- Prevent delayed AI taunt replies from advancing simulation RNG during active
  single-player recording/playback. Their native two-second wall-clock timer,
  speaker selection and chat behavior remain; idle games and multiplayer retain
  the original RNG path.
- Validate exact native timed-command payload lengths before replay loading and
  dispatch, including Crusader's 402-byte and Extreme's 1,252-byte unit-selection
  payloads. Reject truncated/extended layouts even when replay checksums match.
- Remove chat/taunt category 14 from the timed replay allowlist: its native
  handler declares a 544-byte immediate message and resets its timestamp to zero.
  This release does not add chat playback.
- Use simulation profile `recorder-sp-v9`. Make fresh recordings with this
  version; earlier recordings need their original recorder release. This avoids
  silently playing old RNG histories with the new taunt guard.
- Add original-executable tests for command layouts and the complete AI reply
  selection routine on both variants. Multiplayer playback is still unavailable;
  live taunt, Extreme, menu and settings-restart tests remain required.

## 0.22.0

- Reject multiplayer comparisons that use the same logical player twice, omit
  peer identity, or mix starting boundaries, game modes or incompatible headers.
  Native synchronization inspection now applies the same pair checks.
- Add `rngIntervals` to the comparison tool's `--inspect` output: locate the
  first differing RNG caller-count interval separately from the first differing
  RNG/resource checkpoint. Preserve differences even when later counts cancel.
- Validate interval sequences and ending evidence; malformed or interrupted
  captures cannot leave apparently complete interval statistics. Exclude the
  first partial counter window and reject roster/resynchronization transitions.
- These are offline evidence improvements. Native recording and menus are
  unchanged; multiplayer playback remains unavailable. Caller-count differences
  are investigative leads, not proof of which call caused a desync.

## 0.21.0

- Correct multiplayer immediate-message diagnostics to read the game's fixed
  payload buffer. Version 0.20.0 read the unused timed-command payload instead;
  its immediate-message payload bytes must not be used as network evidence.
- Support the fixed buffer's 61,000-byte capacity without changing the smaller
  timed replay limit. Keep malformed sizes isolated from native gameplay.
- Add native synchronization inspection to `--inspect`: decode command 12's
  lag, hash and advertised match tick, compare receipts, and compare all human
  players' advertised hashes at common ticks. Reject legacy payload evidence
  and retain the strict comparator's existing incomplete result and exit code.
- Verify both local and received immediate paths against the original SHC and
  Extreme instructions, including ring endpoints and maximum fixed payloads.

Multiplayer playback remains unavailable. Matching native advertised hashes
provide additional evidence, not proof of a complete or desync-free replay.

## 0.20.0

- Show Replay status in the multiplayer pause menu. Distinguish waiting, active,
  saved and failed test captures, show command/coverage counts, and explicitly
  state when later actions are no longer being saved or replay is unavailable.
- Attribute both native RNG streams to their return addresses between diagnostic
  checkpoints without changing RNG results. Bound caller storage and isolate
  diagnostic failures from multiplayer command execution.
- Preserve immediate-command handles and payloads alongside coverage gaps so
  network messages can be investigated without silently excluding them.
- Document the first two-peer Ascension action test and its limits: matching
  timed commands/resources, divergent RNG stream 1, and incomplete event coverage.

Multiplayer replay remains disabled. Diagnostic evidence is not a playable replay.

## 0.19.0

- Add optional shared start/end ticks for multiplayer diagnostic capture. Both peers can seal the same simulation interval automatically before either leaves the match, while gameplay continues.
- Retain commands queued before the diagnostic window but executed inside it. Keep host/roster/synchronization gaps visible within the window, and do not reopen a sealed trace because of later commands or disconnection.
- Add bounded trace format 6. Require matching windows and the complete sequence through the final RNG/resource checkpoint; early exits, missed boundaries and missing final checkpoints cannot pass comparison, even when both traces have the same omission.
- Cover repeated native ring reuse, AI roster/resource evidence, paused end ticks, early exits, host events and footer write failure in automated tests. Update the live test matrix and document the completed 0.18.0 development SP/Automarket replay tests separately from pending two-peer and Extreme tests.

Validation: 157 automated tests, original-executable checks for Crusader and Extreme, and ZIP packaging pass. Multiplayer replay remains disabled. Bounded diagnostics measure command/RNG/resource agreement over an explicit interval; they do not capture a replayable starting world or prove full-world determinism.

## 0.18.0

- Capture locally generated timed commands directly from the native queue, including troop orders. These bypass the received-packet hook; previously the first order stopped recording with a missing-payload error.
- Share local command observation with multiplayer diagnostics without installing overlapping hooks. Preserve native registers and retain validation before dispatch.
- Accept the verified map-extensions 1.0.0 save wrapper used by the shipped framework (`CALL rel32`), retaining the wrapper and extension snapshot data.
- Resolve the optional UI module's callable entries before installing recorder menu hooks, keeping Automarket's later GUI initialization working.
- Replace old playback reports at each new attempt and report failure or interruption, so repeat tests cannot retain a stale success.

Validation: 148 automated tests and original-executable checks pass for both variants, including 600 local captures and 600 replay dispatches each. Development SHC playback completed twice with two AIs; the Automarket integration replay completed 69,573 ticks and 13 commands with RNG/resource checkpoints matched. See `docs/live-validation-0.18.md` for scope and remaining gates. Multiplayer playback remains disabled.

## 0.17.0

- Record new single-player Skirmishes by default, arming after the lobby validates Start and before match seed initialization. Save the full replay on normal mission exit. Add a default-on UCP option and an Auto: on/off lobby toggle.
- Add Save replay as... to the native pause menu. Save a named, independently sealed copy of the match so far while automatic recording continues; failures leave the source capture intact. Names are bounded metadata and duplicate names never overwrite files.
- Add keyboard name entry, library renaming and save confirmation. Use the game's original tiled button graphics, always-visible gold outlines, hover/selection highlights, font and red modal frames in both executable profiles.
- Make Play choose a recorded-settings restart when required. Keep the normal configuration intact and reject unresolved extension/framework mismatches instead of repeatedly restarting with identical configuration bytes.
- Preserve native pause actions and the pause stack. Share one visibility hook across both menus; consume keyboard messages only while a recorder dialog is active in single-player.

Validation: 142 automated tests pass, including file-copy isolation/failure, default capture lifecycle, actual menu actions, keyboard editing and settings routing. Original hook bytes, pause-menu layout and existing native dispatch/RNG checks pass for Crusader and Extreme. Live rendering/input, complete latest-build playback and settings handoff remain unverified; multiplayer playback remains disabled. SP simulation profile stays `recorder-sp-v8`.

## 0.16.0

- Feed replay commands at the native command-selection boundary when they are due. Remove the receive-loop prefetch hook and its 64-tick lookahead; scheduling no longer depends on how often networking is polled.
- During SP playback, select the entire due batch by recorded execution sequence, preserving native handler execution and player identity. The native physical-ring scan can otherwise reverse same-tick commands when the replay queue wraps.
- Validate all owned entries and reject untracked pending entries before publishing a batch. Check native enqueue completion, copied payload length/source, ring advancement, state, sender, category, tick and payload contents.
- Restore the original ring entry, write cursor and saved scheduling scratch on failed enqueue. Invalidate replay-owned queued entries and the selected batch when playback fails or is cancelled, preventing later accidental execution. This is queue recovery, not rollback of arbitrary native/extension effects.
- Reject more than 100 commands at one execution tick during recording and file preflight. Reproducing multiple native batches at an unchanged tick needs explicit batch-phase evidence; this version fails rather than silently moving commands to another tick.
- Use SP simulation profile `recorder-sp-v8`; old captures require their original recorder version. Idle play, recording, native loading and multiplayer still use the original selector. Multiplayer diagnostic format remains 5 and MP replay is not enabled.

Validation: 128 automated tests, including 1,600-command session completion with 1, 3 and 20 simulated ticks per frame, failed admission, cancellation and multiplayer isolation. Original-executable checks pass for Crusader and Extreme. A new isolated native harness reproduces physical-ring reordering, then runs the Lua engine with each original scheduler/dispatcher for 600 correctly ordered commands per variant and verifies queue rollback after a native size mismatch. Native gameplay handlers and the real UCP bridge still require live testing; the harness uses explicit stand-ins. See [dispatch evidence and limits](docs/replay-dispatch.md).

## 0.15.0

- Observe the native DirectPlay system-message branch in Crusader and Extreme before host/roster/timing mutations. Player removal and host migration bypass timed command dispatch and can no longer silently leave an open diagnostic trace looking complete.
- Log a conservative coverage gap with the message type, declared size and removal handle when present. Do not dereference message pointers or treat the header as a captured/replayable system payload. Even native-ignored and unknown system messages mark this stage incomplete.
- Use multiplayer diagnostic format 5 to distinguish the new coverage from format 4. Mixed-format comparisons are rejected; paired older traces retain their original evidence limits. Single-player simulation profile stays `recorder-sp-v7`.
- Keep the observer opt-in, read-only and isolated from logging/validation failures. This does not implement host migration or player departure in replay, nor enable multiplayer recording/playback.

Validation: 116 automated tests pass, including system events without sampled roster changes, unknown/short messages, write/read validation failures, single-player exclusion and comparison coverage. Original executable checks pass for both variants, including eight native receive-result/sender cases per variant proving this hook is reached only after a successful system-message receive. Live multiplayer behavior and performance remain unverified.

## 0.14.0

- Prevent resource-warning speech, ambient sound selection, audio initialization and battle/ambient music from advancing the simulation RNG during single-player recording and playback. These paths depend on local UI, audio or wall-clock activity that the command stream does not reproduce.
- Isolate RNG advances when selecting heads-on-spikes and choosing the next placement preview. Preserve the queued placement command, including its selected variant, and the preview update.
- Handle the native placement handler's tail jump explicitly: active sessions return to its caller; idle and multiplayer paths still jump to the original RNG function with the original stack and flags.
- Use simulation profile `recorder-sp-v7`. Older recordings need their original module version. Reusing the current RNG value can reduce audio/preview variety; these changes do not alter normal multiplayer behavior or enable multiplayer replay.

Validation: 112 automated tests, exact hook-byte and audited audio-function call coverage checks on both original executables, plus 56 native placement-tail emulation cases per variant checking command contents, preview, RNG state, saved registers and return stack. No new live test is claimed. See [evidence and remaining gaps](docs/presentation-rng.md).

## 0.13.0

- Capture locally queued multiplayer payloads before native transmission; these do not pass through the received-command copy hook and were previously reported as untracked.
- Record the native eight-slot human/AI roster and transport identity in multiplayer diagnostic format 4. Compare logical rosters across peers, while checking each command's handle against its recorded actor.
- Observe both local and received immediate-command execution paths when multiplayer diagnostics are enabled. Mark them as coverage gaps instead of silently omitting them from a supposedly complete trace.
- Detect roster/identity changes and native synchronization phase changes between periodic checkpoints. Traces starting during resync, ambiguous/system handles, uncovered events and incompatible rosters cannot report a successful comparison.
- Preserve normal dispatch instructions/registers and isolate diagnostic errors. The three new native hooks are installed only when the optional diagnostics setting is enabled.
- Document the remaining network requirements, including system-message transitions, chunked resync, 24-bit wire timestamps and private extension state. Single-player profile remains `recorder-sp-v6`; older paired trace formats retain their original evidence limits.

Validation: 112 automated tests, both original executable profiles and ZIP packaging pass. New tests cover local queue capture, roster differences, handle renumbering/ownership, between-checkpoint resync, immediate dispatch, hook conflicts and write-failure pass-through. No live multiplayer validation was performed; this improves diagnostics and does not enable multiplayer recording/playback.

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
