# UCP Recorder

Work in progress: recording and playback of single-player Stronghold Crusader and Crusader Extreme Skirmishes using UCP3.

Version 0.15.0 detects DirectPlay system messages, including player removal and host migration, as explicit gaps in multiplayer diagnostics. It includes 0.14.0's audio/UI RNG isolation for single-player recording and playback. Recordings, the native replay browser and loading a starting save have been exercised in game. **A complete replay with the latest RNG fixes, Extreme gameplay and settings restart still need live verification.** Multiplayer recording is not supported yet; normal multiplayer isolation has automated coverage but still needs a live comparison. See [multiplayer evidence](docs/multiplayer-diagnostics.md), the [presentation RNG audit](docs/presentation-rng.md) and [live findings and next tests](docs/live-validation.md).

Automarket 1.1.0 has an experimental replay adapter for its settings commits and native custom save section. Use protocol 1.0.0 and map-extensions 1.0.0, with **recorder after protocol in the extension order**. The normal weekly trades run in the simulation; they are not replayed as extra trades. Other custom protocols remain unsupported. See [Automarket replay notes](docs/automarket-replay.md).

Optional **Multiplayer diagnostics** logs actual command execution and periodic simulation evidence for comparing two peers. It is disabled by default and does not enable multiplayer replay. See [multiplayer trace instructions](docs/multiplayer-diagnostics.md).

## Testing this build

Use a separate game installation with UCP3 developer mode and this module enabled. If your game needs Graphics API Replacer, keep it and its dependencies enabled in the test configuration.

1. Open a single-player Skirmish lobby and configure the match.
2. Click **Record** near the bottom. This arms a new recording; **Cancel** cancels it.
3. Start the match. The module captures the starting save and begins recording.
4. Leave through **Quit Mission** to finalize the recording. Do not terminate the process to finish a replay.
5. Return to a Skirmish lobby, open **Replays**, select a completed session and click **Play**. The saved starting state replaces manual map/AI setup.
6. If settings differ, click **Queue settings restart**, close the dialog, and exit the game normally. The helper reopens the same game executable with the recorded UCP configuration. Open the Skirmish replay browser again; the requested recording is selected.

Do not delete older recordings to make a new one: every session has a separate folder under `ucp/replays/`. A settings restart leaves your normal `ucp-config.yml` intact. It requires the recorded extension versions to be installed; it does not download dependencies. If the helper fails, inspect `ucp/replays/restart-error.txt`.

On failure, inspect `ucp3.log` and the session's `last-error.txt` or `desync.json`. A failed or cancelled capture cannot be played. Saving/loading during a recording is currently unsupported and fails the capture explicitly.

See [session format and limitations](docs/replay-sessions.md), [browser and restart testing](docs/replay-browser.md), [native port notes](docs/native-port.md) and [changelog](CHANGELOG.md).

## Development

```sh
python -m pip install lupa==2.6 unicorn==2.1.4 capstone==5.0.7
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-0.15.0.zip` with a flat module layout. `definition.yml` uses metadata schema version `1.0.0`; that is separate from the extension version.
