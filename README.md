# UCP Recorder

Record Skirmishes automatically, save named copies while playing, and watch
recordings from **Single Player > Skirmish > Battle history**. Multiplayer matches are
recorded separately on each PC and played back locally in single-player.
There is no multiplayer replay session to join or host.

**Experimental test build:** the code supports Crusader and Extreme. The new
offline multiplayer path completed both the host (288,568 ticks) and independent
client (288,592 ticks) captures from one physical Steam match, each with 3,951
commands and matching RNG/resource checkpoints. An Extreme recording also completed
playback (36,598 ticks). Multiple physical multiplayer matches, connection-loss
recovery and broader testing remain. See the [remaining work](docs/roadmap.md).

## Install and play

1. Follow the **[fresh-machine setup guide](docs/setup.md)**. Download
   `recorder-0.48.7.zip` from this PR's test release, rather than GitHub's source
   archive. Links appear on the [pull requests](https://github.com/Corax34/ucp_recorder/pulls)
   and [publishing fork's releases](https://github.com/Krarilotus/ucp_recorder/releases).
2. Enable recorder in a separate UCP3 test installation. Keep Graphics API
   Replacer enabled if needed. The setup guide covers Ascension, Automarket,
   dependencies and extension order.
3. Recording is **on by default** for new Skirmishes, loaded single-player
   Skirmish saves, and multiplayer matches. The launch option controls automatic recording.
4. **Pause > Save replay** saves a named prefix without stopping the full
   recording. During multiplayer use **Replay status > Save capture as...**.
   Leaving the mission normally saves the automatic recording.
5. Open **Skirmish > Battle history**. Click a row to select it, then use the
   right-pointing **Watch replay** hand. Click the selected row again for native
   statistics. **Rename** and F2 apply only to recordings; old game results remain.
6. During playback, click a portrait on the left to inspect that player's reports.
   Tick/status stays visible at the top right; F3 toggles date, game/framework
   versions and active packs. Use the normal Escape menu to resume or leave.
   Mission restart is disabled during playback.
   Speed keys and the HUD minus/plus buttons reuse the installed game's speed
   policy, including UCP2-Legacy's extended limits. At completion, **Statistics**
   leaves the world and opens this recording's native history statistics.

All new recordings are stored under `ucp/replays`. Earlier multiplayer diagnostic
captures remain under their original directories; they lack the new tick data
and are not converted into playable recordings. Do not terminate the process to
finish a recording. See [multiplayer playback and recovery](docs/offline-multiplayer.md)
and [menu controls](docs/replay-menus.md).

See the [in-game previews](docs/replay-menus.md#in-game-previews) for native history,
player portraits and playback information.

The `3.0.7` extension-store integration is being prepared for wider testing. Once
published there, choose **UCP-Recorder 0.48.7** through the store; the store build
uses the same release file selection and includes all nine UCP languages. Its
signed ZIP may have a different archive fingerprint from a PR download. Keep the
exact package used for each recording; do not substitute it during playback.

## Recorded settings

Each replay includes its resolved UCP options, exact versions and load order,
plus fingerprints of extension files and readable configured assets. If Play
needs another configuration, it queues a restart: exit normally, let the helper
relaunch, then select Play again. Your normal configuration is preserved.

Required versions must already be installed. Missing versions or changed assets
are reported; a newer version is not silently substituted. The helper does not
download unavailable releases. See [recorded settings](docs/recorded-settings.md).

## Troubleshooting

- Keep a failed replay and its `last-playback.json`, `desync.json` or
  `last-error.txt`. A playback failure halts the replay; a recording failure
  detaches recording so the live match can continue.
- `Recorder session hook conflicts at save` in **0.17.0** was fixed in 0.18.0.
  Install the published package, not the source ZIP. Switching executables does
  not update the module.
- `ucp/recorder-startup.txt` records loaded versions/order and startup status.
  **READY** means initialization succeeded, not that a replay has been verified.
- Launcher options cover all nine UCP languages. In-game text currently supports
  English/German; the original bitmap fonts limit additional script coverage.

Further details: [compatibility](docs/extension-compatibility.md),
[RNG diagnosis](docs/rng-attribution.md), [command coverage](docs/command-coverage.md),
[Automarket](docs/automarket-replay.md), [native world conversion](docs/multiplayer-world-state.md),
and [changelog](CHANGELOG.md). Older successful live tests do not establish that
this build or every module combination works.

## Development

```sh
python -m pip install lupa==2.6 unicorn==2.1.4 capstone==5.0.7
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-VERSION.zip` with a flat module layout.
The extension version and `meta.version: 1.0.0` (definition schema) are separate.

Runtime ownership, current costs and Linux limitations are described in
[runtime and performance](docs/runtime-and-performance.md).
