# Remaining replay work

The five implementation areas remain the scope. Code completion and live proof
are separate; unverified behavior is not marked complete.

| Area | Implemented | Still required |
| --- | --- | --- |
| Native world restoration | SHC/Extreme header, codec, original reader and post-preparation restoration | Live loaded-save and recovery-world comparison |
| Offline multiplayer | Human roster/actor translation, timed commands, transport isolation, local SP browser | Host and client replay completion with AIs and Automarket |
| Connection recovery | Stable replacement worlds, linked intervals, independent named copies, prefix retention | Controlled loss/resync/host departure across multiple games |
| Determinism/settings | Tick/command RNG checks, exact config/restart, asset fingerprints | Prove earlier RNG2 failures resolved; audit remaining module-owned state |
| Menu integration | Native fonts/skin, library, naming/removal, pause/speed/player views | Ghost-preview/input audit, report navigation, more in-game languages, real current screenshots |

Launcher translations cover all nine languages; in-game translations currently
cover English/German. Ghidra confirms that the supported executable's wide-text
entry still converts to the same bitmap glyph table. Calling it alone does not
provide missing Cyrillic, Chinese or Persian glyphs.

Run the focused live matrix after the remaining input/state work is ready. Keep
failed recordings and telemetry; do not infer correctness from initialization
or a single untouched AI match.
