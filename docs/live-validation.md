# Live validation: 0.12.0 development

Tests on 2026-09-05 used an isolated Crusader installation with Graphics API Replacer, fixed seed 123 and replay checkpoint tracing. The final patch is ready for another test; these observations do not certify complete playback.

## Observed results

- Record/Cancel and the native Replays dialog rendered and accepted input in the single-player Skirmish lobby after font and hit-box repairs. The final text-shadow addition is covered by code inspection, not a new screenshot.
- Native starting saves and recording files were created and finalized through Quit Mission. A capture reached tick 6,619 with speed raised from 36 to 300.
- The browser selected a completed recording and loaded its starting save. Playback stopped on RNG mismatches instead of silently continuing.
- A timing experiment captured at tick 2, passed the complete RNG/resource checkpoint at tick 64, then failed at tick 128. This does not establish that delaying capture solves desyncs. The shipped change captures at the first simulation boundary; it does not discard an arbitrary initial tick.
- All these live captures had zero recorded player commands. They cannot establish command playback correctness.

## Native causes and repairs

The original resource-name functions are leaf functions whose callers retain ECX/EDX. Lua hooks preserved the public calling convention but clobbered registers expected by a caller at `0x471C10`, causing a lobby crash at `0x471C31`. Native trampolines now preserve registers and flags on the normal path and override only the return value during snapshot loading.

The old pause-camera patch covered `0x45CE36`, an incoming unpaused branch target, causing an invalid-instruction crash at the first tick. The guard now replaces the preceding complete comparison at `0x45CE2D` (`0x45D03D` in Extreme). An x86 regression test enters through the earlier branch and checks paused, unpaused, idle and multiplayer paths.

UCP's library loader cannot load arbitrary system DLLs, `allocateCode` does not resolve an assembly-lambda table directly, and `writeString` does not append a NUL byte. The Windows adapter now resolves GetProcAddress through loaded PE exports, assembles the calling-convention bridge using writeCode, and explicitly terminates reused buffers. Forwarder and path-reuse tests exercise both import profiles.

## Music and the RNG mismatch

A temporary local call-site trace captured the usual once-per-tick RNG1 call returning to `0x45CE58`, plus two extra calls at tick 76 returning to `0x47A34F` and `0x47A493`. Ghidra identifies both inside `SoundSystem::selectAndPlayMoodBasedMusic` at `0x47A340`; the corresponding Extreme function starts at `0x47A510`.

OpenSHC already has a compatible implementation in `src/OpenSHC/Audio/mss/SoundSystem/selectAndPlayMoodBasedMusic.cpp`. It confirms that track selection consumes the match RNG. Audio-driven timing is therefore a concrete source of RNG advancement outside the recorded simulation inputs. This explains a drift mechanism; a final successful replay is still needed to demonstrate that no other source remains.

The previous three music guards missed all seven calls in this function:

| Call | Crusader | Extreme |
| --- | --- | --- |
| 1 | `0x47A34A` | `0x47A51A` |
| 2 | `0x47A3B0` | `0x47A580` |
| 3 | `0x47A3CF` | `0x47A59F` |
| 4 | `0x47A3F3` | `0x47A5C3` |
| 5 | `0x47A422` | `0x47A5F2` |
| 6 | `0x47A446` | `0x47A616` |
| 7 | `0x47A48E` | `0x47A65E` |

During an active single-player recorder session these calls are skipped. The following native instructions read the existing current RNG value, so music selection remains enabled without advancing simulation randomness. Track variety may change. Idle and multiplayer execution retain every original call. The optional executable checker disassembles the whole function and requires exact coverage of all seven calls; x86 tests compare native and gated register/flag/stack behavior.

Original executable SHA-256 identities used for these checks:

- Crusader: `3bb0a8c1e72331b3a30a5aa93ed94beca0081b476b04c1960e26d5b45387ac5a`
- Extreme: `55648e6b05d67d37a5773fe699bbb17a2d6ad4de1bb9dbded9a21caef82bd7fb`

The temporary per-call RNG trace is not included in the release. The current-resource address was checked against OpenSHC and Automarket and remains unchanged; goods awaiting delivery are not the player's current resource array.

## Next live gates

1. Install the published 0.12.0 ZIP and make a fresh capture; development captures from timing experiments are not acceptance evidence for this build. Replay a command-free match through completion, including several music changes, then replay it again.
2. Capture building, trading, unit orders, pause and game-speed changes. Check both the completion report and visible outcomes. UCP2 extended speed limits and the plus key can accelerate tests when enabled; compare different recording/playback speeds too.
3. Repeat on Extreme, then exercise the Automarket adapter and saved-settings restart with their required extensions.
4. Compare two peers using the existing opt-in multiplayer diagnostics. Multiplayer replay stays disabled until command ownership, resynchronization, initialization and non-command simulation inputs have been validated.

Full-world checksums and content fingerprints for external assets/extensions remain separate gaps. Matching RNG and resource checkpoints alone is not proof that every entity or extension state matches.
