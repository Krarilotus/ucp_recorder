# UCP Recorder

Record a single-player Skirmish, save named copies while you play, and watch it
from the game's **Replays** library. Recording is on by default. Replay buttons
use the original interface skin, gold font and red dialog frames.

**This is an experimental test build. Multiplayer playback is not implemented.**
Crusader and Extreme have native ports, but the latest published build, Extreme
gameplay and the recorded-settings restart still need live verification.

## Install and try it

1. Follow the **[fresh-machine setup guide](docs/setup.md)**. Download the
   `recorder-0.26.0.zip` asset from this PR's test release, not GitHub's source ZIP.
   Release links are posted on the [pull requests](https://github.com/Corax34/ucp_recorder/pulls);
   assets are hosted in the [publishing fork's releases](https://github.com/Krarilotus/ucp_recorder/releases).
2. Enable recorder in a separate UCP3 test installation. Keep Graphics API
   Replacer enabled if your game needs it. The setup guide covers Ascension and
   Automarket versions and extension order.
3. Open **Single Player > Skirmish**, check **Auto: on**, and start a new match.
4. Use **Pause > Save replay as...** to name a copy of the match so far. Recording
   continues. **Quit Mission** saves the full recording automatically.
5. Open **Skirmish > Replays**, select a completed recording and click **Play**.
   **Rename replay...** changes a completed recording's display name.

Recordings have separate folders under `ucp/replays/`. Do not terminate the game
process to finish a recording. Native game saves/loads during capture are
unsupported; use **Save replay as...** for a replay copy.

If Play needs different settings, it queues a restart. Exit normally; the helper
reopens the same executable with the recorded extension versions, order and
resolved options. Open **Skirmish > Replays** again and click **Play** on the
selected recording. Your normal configuration is preserved. Required extension
versions must already be installed; the helper does not download them.
See [recorded settings](docs/recorded-settings.md).

## Troubleshooting and test status

**`Recorder session hook conflicts at save` in 0.17.0:** update to this PR's
published package. Version 0.18.0 fixed rejection of map-extensions 1.0.0's CALL
save wrapper. Switching between Crusader and Extreme does not update the module.

Version 0.26.0 writes `ucp/recorder-startup.txt` with loaded versions/order and
the startup result. Optional multiplayer diagnostic sites are checked before
recorder installs hooks. Conflicting hook reports include addresses and
expected/actual bytes. `READY` means initialization succeeded, not replay
validation. See [setup and error reporting](docs/setup.md) and the
[changelog](CHANGELOG.md).

Development 0.18.0 Crusader playback completed twice with two AIs. A separate
Automarket match replayed 69,573 ticks and 13 commands with matching RNG/resource
checkpoints; named-save controls were exercised. These earlier tests do not
establish that every subsequent build or mod combination works.

A published 0.19.0 two-peer Ascension test captured 63 identical timed commands
and 241 matching resource checkpoints, but RNG stream 1 differed and immediate
messages left coverage incomplete. **Multiplayer diagnostics** is an opt-in
investigation tool, not a playable multiplayer recording. See
[multiplayer findings](docs/multiplayer-findings.md),
[capture instructions](docs/multiplayer-diagnostics.md) and the
[harder test matrix](docs/multiplayer-test-matrix.md).

Fresh recordings use simulation profile `recorder-sp-v9`. Keep older packages for
older captures. Further details: [session limitations](docs/replay-sessions.md),
[Automarket integration](docs/automarket-replay.md), [native port](docs/native-port.md),
[library flow](docs/replay-library.md), [dispatch](docs/replay-dispatch.md),
[world hashes](docs/native-world-hashes.md) and
[paired capture analysis](docs/multiplayer-comparison.md).

## Development

```sh
python -m pip install lupa==2.6 unicorn==2.1.4 capstone==5.0.7
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-0.26.0.zip` with a flat module layout.
`definition.yml` uses metadata schema version `1.0.0`; that is separate from
the extension version `0.26.0`.
