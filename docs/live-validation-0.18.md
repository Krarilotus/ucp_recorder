# Live validation: 0.18.0 development

These tests use an isolated SHC installation, Graphics API Replacer 1.3.0, fixed seed 123, and the original executable identities listed in `live-validation.md`. Development ZIPs are distinguished from published PR builds below. Matching RNG and resources does not certify the entire world state or multiplayer determinism.

## Local command capture

The published 0.17.0 build stopped on the first troop-selection/order sequence at tick 5,148 (`20260906-022910-0001`): `Native command has no captured payload/ownership`. Locally generated timed commands enter the ring without traversing the received-packet copy hook. Capture now observes the completed local payload before transmission advances the write cursor.

With that repair, an automatically recorded Skirmish against Rat and Saladin reached tick 17,183 with four selection/deselection/move commands. Save replay as created an independent named copy while recording continued; normal mission exit sealed the source. The named copy played through completion twice in the same process, matching every full RNG and resource checkpoint plus the final checkpoint. One playback included pause/status/resume. The visible troop move matched the recording.

Session IDs: source `20260906-023505-0001`; named copy `20260906-023631-0001`, display name `a`. Both playback reports contain `status: finished`, `commands: 4`, `lastTick: 17183`. These runs used the development command-capture repair before the later report-lifecycle and Automarket compatibility changes.

The native regression also runs the original scheduler, selector, translator, dispatcher and local queue from both executable variants. It captures 600 local commands without any received-copy callback, wraps the 200-entry ring, and checks ownership, payload and native execution order. The existing 600-command replay and failed-enqueue rollback cases pass. UCP bridges, transport and a four-byte command handler are harness substitutes; this is not a live multiplayer test.

## Automarket integration

The profile adds LuaJIT 1.0.0, cffi 1.0.0, UI 1.0.1 development, protocol 1.0.0, map-extensions 1.0.0 and Automarket 1.1.0 before recorder.

- UI 1.0.0 has a real one-past-the-end menu-array write/read. The independent UI 1.0.1 repair is [UI PR #6](https://github.com/gynt/ucp-extension-ui/pull/6), with a bounded regression and published test ZIP.
- The shipped map-extensions save hook uses `CALL rel32`, while recorder accepted only `JMP rel32`. Recorder now accepts either verified wrapper form without replacing it, and still checks the untouched byte and required module version.
- Automarket resolves main-state UI callables in its later GUI callback. Recorder now resolves the optional UI interface before hooking modal activation, retaining the callable entry and preventing the later signature scan from failing.

The corrected profile reaches the lobby and records `20260906-030204-0001` with Rat and Saladin. The user-facing Automarket toggle, wood sell rule and Save & Close produce a captured 272-byte category-122 command. Building a market then sells wood from 95 to 8 and raises gold from 2,000 to 2,087. AI attacks destroy the market and defeat the human player. Normal exit seals a 69,572-tick recording.

Playback finishes at tick 69,573 with all 13 commands and every RNG/resource checkpoint matching. Attempted spectator selection and move input draws the native selection/target feedback but does not move troops or change the simulation. That misleading command feedback remains a UI polish issue. This run used all 0.18.0 runtime repairs described above, with development ZIPs.

## Remaining live gates

Repeat complete playback with the final published ZIP, then on Extreme. Exercise different playback speed, recorded-settings relaunch, Automarket buys/fees and additional game commands. Two genuine peers are required for the multiplayer diagnostics; multiplayer playback remains disabled pending the reconstruction work documented in the networking analysis. Full-world checksums and content fingerprints remain separate gaps.
