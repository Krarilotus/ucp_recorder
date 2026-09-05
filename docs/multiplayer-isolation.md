# Multiplayer isolation (0.5.0)

The module previously installed unconditional RNG and gameplay patches, even with recording disabled. Its single-player start guard did not protect normal multiplayer from those changes.

Each simulation patch now checks a recorder-owned scope flag and the native mode (`0` or `99` for single-player). All other modes execute the original instructions. A stale scope flag therefore cannot apply the changes in multiplayer. The fixed seed and tick observer use the same gates; the multiplayer tick path ignores a stale halt flag and does not call Lua recording code.

Arming recording enables the scope; playback enables it only after preflight. Reset clears it before file finalization. A transition into multiplayer aborts the capture and closes files without writing the multiplayer pause flag. The command-queue guard independently checks single-player mode before blocking playback input.

## Native equivalence checks

`scoped-sites.lua` records complete original instruction sequences for both variants, extending the old one/two-byte branch checks to full instructions. `scoped-code.lua` emits and relocates calls/conditional branches explicitly: UCP's `core.insertCode` copies original bytes without fixing their relative destinations.

The emulator executes the original and generated sequences and compares registers, flags, stack, destinations and observable callee effects. Cases cover idle single-player, multiplayer with both scope values, conditional flag combinations, stack-cleaning dust calls, fixed-seed writes and multiplayer with a stale halt flag. This demonstrates equivalence of the guarded sequences; it is not an emulation of a whole multiplayer match or proof that all other modules are compatible.

## Menu integration

Ghidra's `Menu::handleMenuItems` skips negative item types in its input and rendering passes. The recorder applies that state only to its own controls when multiplayer is active, then restores normal type `3` in single-player. It identifies controls by their callbacks in the current owning menu array, preserving appended items and accommodating array reallocation. It does not insert a terminator that would hide another extension's controls.

The native guard is installed before menu traversal. Action callbacks also check game mode. Modal rendering, placement and navigation still need visual tests.

## Next gaps

Multiplayer recording needs all executed commands with actor identities, a defined initial-state boundary, and a strategy for multiplayer-only simulation behaviour during playback. Automation and extension state must be captured explicitly; version names alone are insufficient. Save/autosave handling, world-state verification and real capture/load/playback comparisons remain separate work.
