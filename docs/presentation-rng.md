# Presentation RNG audit (0.14.0)

Playback dispatches game commands at simulation boundaries. It does not reproduce every toolbar click, failed placement attempt, audio callback or elapsed wall-clock interval. If one of those paths advances the same RNG used by simulation, restoring its initial state and replaying commands is insufficient.

This stage guards eight additional RNG1 advances during active single-player recorder sessions. It leaves each surrounding routine running and reuses the current RNG value for presentation choices. Track, ambient-sound and preview variety may decrease. This is an explicit simulation profile change (`recorder-sp-v7`), not compatibility with old captures.

## Audited native sites

The addresses below were checked against both original executables. Function and field names refer to the OpenSHC-labelled Crusader Ghidra database; names alone are not proof of a call's effects. The surrounding instructions and command data flow were inspected as well.

| Behavior | Crusader RNG call | Extreme RNG call | Why the replay stream misses it |
| --- | --- | --- | --- |
| Ambient sound tie-breaking | `44C272` | `44C4A2` | Audio update uses elapsed time and local stream priorities. |
| Missing-resource speech | `47176B` | `47198B` | A rejected UI action can play speech without a queued command; current playback command execution cannot recreate that attempt. |
| Audio launch initialization | `47A157` | `47A327` | Sound initialization consumes RNG between presentation choices. Save loading and launching a fresh match need not call it at the same boundary. |
| Battle music selection | `47AE06`, `47AE5C` | `47AFD6`, `47B02C` | Local audio transition chooses music tracks. |
| Ambient music selection | `47BE45` | `47C015` | A branch explicitly tests a `timeGetTime()` interval greater than 30,000 ms before consuming RNG. Simulation tick equality does not imply wall-clock equality. |
| Heads-on-spikes toolbar selection | `444868` | `444A98` | Selecting a tool updates the local preview before any placement command exists. |
| Next heads-on-spikes preview | `445777` (tail jump) | `4459A7` (tail jump) | The placement command already contains the selected variant; the subsequent RNG advance prepares local UI state. |

For heads-on-spikes, native code stores the selected variant in command parameter 5, queues `GCT_SPAWN_ENTITY` (`0x45`), computes the next preview as current RNG1 modulo 7, restores the caller's saved registers, then tail-jumps to RNG1. The new gate must return from that handler when suppressing the tail call. Jumping to the instruction after the tail would enter a different placement branch with an already-unwound stack.

The audio-launch routine also resets other match/audio counters. Only its RNG call is gated; skipping the whole routine would discard those effects. The ordinary simulation-tick RNG advance and gameplay callers such as fire, damage, marriage and unit updates remain intact. A global RNG suppression patch would break simulation.

## Scope and evidence

The gates check both the recorder's active flag and native game mode (`0` or `99`). Idle sessions and multiplayer retain the original calls/tail jump. Every site is verified before installation; an incompatible or already-patched instruction causes a conflict error.

- `tests/test_scoped_code.py` emulates all gates with varying incoming flags and modes, comparing idle/multiplayer results with the original instruction sequences. Active tail-call suppression checks return destination, stack, registers and flags.
- `tests/check_executables.py` validates exact site bytes in Crusader and Extreme and decodes all RNG calls in the five newly audited audio routines, as well as the earlier mood-music routine. This catches omitted calls within those ranges, rather than merely checking the sites already listed.
- `tests/check_presentation_native.py`, invoked by that executable check, runs each game's original command/preview suffix and original RNG routine in Unicorn. It observes the queue call and checks all six command parameters, preview output, saved registers, return stack and full RNG structure. Seven RNG inputs exercise both active SP modes and unchanged idle/MP behavior, including native index wrap: 56 runs per variant.

These are code and emulation results. They do not establish a successful end-to-end live replay. The earlier in-game trace established extra mood-music RNG calls; the additional paths here were identified through native analysis, not newly reproduced in game.

## Next live checks and remaining limits

Record and replay a match that lasts long enough for music changes, attempts unaffordable building placements, selects/cancels heads-on-spikes, and places several variants. Include actual player commands and compare through completion, then repeat on Extreme and at different game speeds. A prior no-command recording passing one checkpoint is not sufficient.

This does not finish the RNG audit: menu/lobby transitions, AI chat, remaining RNG2 callers, spectator UI side effects and extension state still need investigation. RNG equality is useful divergence evidence, not a full-world checksum. Multiplayer additionally needs a synchronized starting snapshot, complete immediate/system-event handling, resync semantics and per-peer testing. These SP guards are deliberately inactive there; they do not claim to solve multiplayer determinism.

Original executable SHA-256 values:

- Crusader: `3bb0a8c1e72331b3a30a5aa93ed94beca0081b476b04c1960e26d5b45387ac5a`
- Extreme: `55648e6b05d67d37a5773fe699bbb17a2d6ad4de1bb9dbded9a21caef82bd7fb`
