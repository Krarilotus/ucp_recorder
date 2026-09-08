# Extension compatibility and required settings

Recorder has no mandatory dependency on Ascension, Automarket, Steam multiplayer,
UCP2 Legacy, a texture pack, or the `ui` module. Keep the graphics wrapper your
installation needs. Installing recorder does not install other extensions or
change their gameplay options. Automatic recording is on by default; caller-level
RNG diagnostics are optional and off by default. A fixed starting seed is optional:
playback restores the saved RNG state rather than relying on a repeated seed.

## Startup and extension order

Enable recorder after the other native modules in the launcher. In particular,
Automarket's protocol and save handlers must exist before recorder checks them.
UCP's module proxies can exist before their modules are enabled, so presence alone
is not evidence that a shared hook or protocol has been initialized.

The executable's PE header selects the Crusader or Extreme address layout. Each
component then verifies the native bytes it uses, before recorder installs hooks.
An unused fixed-seed hook imposes no byte requirement. Optional caller diagnostics
check their own sites only when enabled. Required simulation and lifecycle checks
remain strict; the header fingerprint does not certify the entire executable.

A failed check writes `DISABLED` to `ucp/recorder-startup.txt` and displays UCP's
existing error dialog: **no replay will be recorded during that launch**. The
game can continue without recorder hooks. This is failure containment, not proof
that the conflicting combination supports replays. Send the report and `ucp3.log`.
The report contains versions, stages and byte differences, not configuration values.
If installation has already begun, a failure remains fatal: partial native patches
cannot safely be treated as an ordinary disabled module. Restart after fixing it.
A `READY` report confirms installation, not a successful full-match replay.

## Source audit, 8 September 2026

The inventory covers all 27 module entries in store branch `3.0.7` at
`cfbca47b6c39b33f84baf5d88406b26f6eb0c342`. The 40 plugin entries were inventoried
by metadata; their assets and option combinations have **not** all been verified.
Source collection and searches are not an exhaustive semantic audit or a test of
every combination. Compiled dependencies and arbitrary future versions need their
own evidence. In particular, do not infer compatibility from an absent literal
address: modules also locate code through AOB patterns and compute patch offsets.

| Modules / path | Replay consideration |
| --- | --- |
| Automarket 1.1.0, protocol 1.0.0, map-extensions 1.0.0 | The inspected store sources have one external custom-protocol/save-section consumer: Automarket. Its reviewed adapter validates the discriminator, payload size, player and fee. Single-player saves call the wrapped save entry; multiplayer starting-world evidence captures its separate state. Unknown versions/layouts are not silently accepted. |
| `ui`, `luajit`, `cffi` | Optional shared infrastructure. Recorder uses native game menus directly. When `ui` is active, its lazy callable entries are resolved before recorder wraps activation. Its existing dependency chain must remain installed. |
| `ucp-autoclick` | Produces mouse input; native command capture is the intended boundary. Playback input isolation still needs a live check with autoclick enabled. No second click recorder should be added. |
| UCP2 Legacy seed option | Reads a live seed file and has private cache state. Keep the same option profile; recorder does not enable or overwrite this option. A file outside the captured settings remains an external input to investigate. |
| UCP2 Legacy `o_onlyai` | Changes player identity and the native load path. Recorder's current player validation does not establish spectator-slot-zero compatibility. A separate restore/identity implementation is required; do not disable ownership checks to accept it. |
| UCP2 Legacy healer / running-units / citizens / workers / rebalancer / ai-ox-tethers | Change simulation code, spawning, timing or tables. Preserve exact enabled options. Matching command streams alone do not prove RNG and world-state equivalence. Recorder does not force these gameplay options off. |
| aiSwapper / aicloader / aivloader / aiv-troops-behaviour / hopfarm-limit-fix | AI definitions, castle/troop setup and behaviour affect the starting world and subsequent simulation. Exact versions and resolved options are recorded; changed external AI files are not yet certified by a content manifest. |
| custom-skirmish-trails / maploader / startResources | Mission setup and external map/trail data affect initial state. Trail-specific runtime registries and load fixups require further restore analysis; Skirmish testing does not certify every trail. |
| files / gmResourceModifier / textResourceModifier / graphicsApiReplacer / winProcHandler | File, rendering, text and input infrastructure. Keep installed assets and dependencies. Visual/input compatibility still needs pixel and interaction tests with the actual wrapper and selected game language. |
| steam-multiplayer | Owns transport and lobby behaviour. Capture observes executed commands and sync evidence on each PC. It does not reimplement Steam transport, recover lost commands, or enable offline multiplayer playback. |

Recorder stores loaded extension versions/order and resolved options. Those values
do **not** prove that mutable maps, AI files, injected DLLs or private extension
state are identical. Native snapshot sections and the Automarket adapter are
explicitly bounded. These gaps must be closed before claiming general multiplayer
restoration, especially across reconnects or world replacement after a desync.

## Pinned module inventory

Each link is the exact source commit inspected/collected, not the repository's
moving default branch. Modules sharing a source archive have separate store entries.

| Module | Store version | Pinned source |
| --- | --- | --- |
| aiv-troops-behaviour | 0.2.3 | [b20dad69257d](https://github.com/Krarilotus/ucp3-fixes/tree/b20dad69257dc94dcfaf8a867a0848d1fccc3252) |
| hopfarm-limit-fix | 0.1.2 | [63219fdeb152](https://github.com/DanielFleger/ucp3-fixes/tree/63219fdeb152f88a17f2ac46040079017fe1251d) |
| ucp-autoclick | 1.0.1 | [a4ecab44c79b](https://github.com/americanpotato/ucp-autoclick/tree/a4ecab44c79bdc9f7d387746e235db9d7be57091) |
| aiSwapper | 1.3.0 | [7ab40c05c0b4](https://github.com/UnofficialCrusaderPatch/extension-aiSwapper/tree/7ab40c05c0b4250f66733645d5e6fabbe036e491) |
| aicloader | 1.1.2 | [b4942485293b](https://github.com/UnofficialCrusaderPatch/extension-aicloader/tree/b4942485293b308ddb54e8a8ab93743b36d6a79b) |
| aivloader | 1.0.0 | [e5afeb5771b8](https://github.com/UnofficialCrusaderPatch/extension-aivloader/tree/e5afeb5771b813cf1f594806f16b53c1c3d476c5) |
| files | 1.3.0 | [8e48fe8b53db](https://github.com/UnofficialCrusaderPatch/extension-files/tree/8e48fe8b53dbb85a7672e4d36744163fc266a5a3) |
| gmResourceModifier | 0.2.0 | [019039afcb29](https://github.com/TheRedDaemon/ucp_gmResourceModifier/tree/019039afcb29f3806aa30c7157ae5a1253c06673) |
| graphicsApiReplacer | 1.3.0 | [f180062e1062](https://github.com/TheRedDaemon/ucp_graphicsApiReplacer/tree/f180062e10622900f684c3de7f76e37dcbdcf304) |
| maploader | 1.1.0 | [1045d6796460](https://github.com/UnofficialCrusaderPatch/extension-maploader/tree/1045d679646051f110cc81e86aebe0b9bce11beb) |
| startResources | 1.0.1 | [71e6d7c2a969](https://github.com/gynt/ucp-extension-startResources/tree/71e6d7c2a9691c2110a2e823501ab9c4510d537f) |
| textResourceModifier | 0.3.0 | [5ab58faf03c4](https://github.com/TheRedDaemon/ucp_textResourceModifier/tree/5ab58faf03c47c16f7b23cb6bc651317edf23728) |
| ucp2-legacy | 2.15.1 | [04e826d00f1a](https://github.com/UnofficialCrusaderPatch/extension-ucp2-legacy/tree/04e826d00f1a5f8a623e15acffc743f115ee7fb1) |
| winProcHandler | 1.0.0 | [5f85672b063a](https://github.com/UnofficialCrusaderPatch/ucp_winProcHandler/tree/5f85672b063a0687d24990f96117d1fbae33af04) |
| running-units | 1.0.2 | [8cbfdf7ef284](https://github.com/gynt/ucp-extension-running-units/tree/8cbfdf7ef2846d16dd5dda0a18ba4937aae59ed1) |
| rebalancer | 1.1.3 | [b3e1a36020b6](https://github.com/CIO61/rebalancer/tree/b3e1a36020b6b00f06a6799d3ede09a4dd5067a5) |
| citizens | 1.0.1 | [46c9af6daaad](https://github.com/gynt/ucp-extension-citizens/tree/46c9af6daaad564de229cfbd2b8e2739e2b96934) |
| custom-skirmish-trails | 1.2.6 | [7afdbd93db2d](https://github.com/gynt/ucp-extension-custom-skirmish-trails/tree/7afdbd93db2d1c432cfb04ee2cac568f6254c462) |
| workers | 0.0.1 | [e7a629c03130](https://github.com/gynt/ucp-extension-workers/tree/e7a629c031308fe1b9dca467213f4e1b943479db) |
| ai-ox-tethers | 1.0.3 | [fc1209d6dd55](https://github.com/gynt/ucp-extension-ai-ox-tethers/tree/fc1209d6dd55b4f1ff9496f50b0f66ee81f97983) |
| map-extensions | 1.0.0 | [d9399125831c](https://github.com/gynt/ucp-extension-map-extensions/tree/d9399125831c96a46701a510542e09f2a031971f) |
| protocol | 1.0.0 | [30f34ee79e05](https://github.com/gynt/ucp-extension-protocol/tree/30f34ee79e0585f05b2729d01b192de374d0bae5) |
| cffi | 1.0.0 | [80c70e2c6b42](https://github.com/gynt/ucp-extension-cffi/tree/80c70e2c6b423742b682d78810b703d49c4c6410) |
| luajit | 1.0.0 | [5b1e7f21c5e5](https://github.com/gynt/ucp-extension-luajit/tree/5b1e7f21c5e5db41a10937a81cf016169dc50067) |
| ui | 1.0.0 | [24f90be8b288](https://github.com/gynt/ucp-extension-ui/tree/24f90be8b2886eb66dea6437fe6016a51bea9a06) |
| automarket | 1.1.0 | [858890f558fd](https://github.com/Krarilotus/ucp-extension-automarket/tree/858890f558fd042215913e862745d98ed13d8834) |
| steam-multiplayer | 1.2.3 | [18c71b7cf10b](https://github.com/gynt/ucp-extension-steam-multiplayer/tree/18c71b7cf10ba9ba3cc07a5c464dc463a6382bd4) |
