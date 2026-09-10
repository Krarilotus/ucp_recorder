# Remaining replay work

The five implementation areas remain the scope. Code completion and live proof
are separate; unverified behavior is not marked complete.

Use the [execution-phase and restore audit](execution-phases.md) to order the
remaining work. The maintenance-phase correction passed a fresh short SP replay;
broader phase/restoration equivalence remains a gate before claiming full
offline-MP completion.

| Area | Implemented | Still required |
| --- | --- | --- |
| Native world restoration | SHC/Extreme header, codec, original reader and post-preparation restoration; SHC loaded-save continuation completed offline | Extreme live and recovery-world comparison |
| Offline multiplayer | Human roster/actor translation, timed commands, transport isolation, local SP browser; host and client captures from one physical Steam match both completed offline | More matches, Extreme and recovery coverage |
| Connection recovery | Stable replacement worlds, linked intervals, independent named copies, prefix retention | Controlled loss/resync/host departure across multiple games |
| Determinism/settings | Tick/command RNG checks, exact config/restart, asset fingerprints | Prove earlier RNG2 failures resolved; audit remaining module-owned state |
| Menu integration | Native battle history, snapshot statistics, rename/right hand, portraits and F3 HUD, packaged screenshots; SHC visual checks | Paused-report correction live check, more in-game languages, offline-MP winner caption |

Launcher translations cover all nine languages; in-game translations currently
cover English/German. Ghidra confirms that the supported executable's wide-text
entry still converts to the same bitmap glyph table. Calling it alone does not
provide missing Cyrillic, Chinese or Persian glyphs.

Run the focused live matrix after the remaining input/state work is ready. Keep
failed recordings and telemetry; do not infer correctness from initialization
or a single untouched AI match.
