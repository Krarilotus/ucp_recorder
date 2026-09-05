# UCP Recorder

Work in progress: recording and playback of single-player Stronghold Crusader and Crusader Extreme Skirmishes using UCP3.

Version 0.4.0 adds a native replay browser and settings restart to individual sessions, starting saves and settings snapshots. **The new save/load playback path, browser rendering and real restart still need in-game verification.** Multiplayer is not supported yet.

## Testing this build

Use a separate game installation with UCP3 developer mode and this module enabled. If your game needs Graphics API Replacer, keep it and its dependencies enabled in the test configuration.

1. Open a single-player Skirmish lobby and configure the match.
2. Click **Record next match** near the bottom. This arms a new recording; **Cancel recording** cancels it.
3. Start the match. The module captures the starting save and begins recording.
4. Leave through **Quit Mission** to finalize the recording. Do not terminate the process to finish a replay.
5. Return to a Skirmish lobby, open **Replays**, select a completed session and click **Play**. The saved starting state replaces manual map/AI setup.
6. If settings differ, click **Queue settings restart**, close the dialog, and exit the game normally. The helper reopens the same game executable with the recorded UCP configuration. Open the Skirmish replay browser again; the requested recording is selected.

Do not delete older recordings to make a new one: every session has a separate folder under `ucp/replays/`. A settings restart leaves your normal `ucp-config.yml` intact. It requires the recorded extension versions to be installed; it does not download dependencies. If the helper fails, inspect `ucp/replays/restart-error.txt`.

On failure, inspect `ucp3.log` and the session's `last-error.txt` or `desync.json`. A failed or cancelled capture cannot be played. Saving/loading during a recording is currently unsupported and fails the capture explicitly.

See [session format and limitations](docs/replay-sessions.md), [browser and restart testing](docs/replay-browser.md), [native port notes](docs/native-port.md) and [changelog](CHANGELOG.md).

## Development

```sh
python -m pip install lupa==2.6 unicorn==2.1.4
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-0.4.0.zip` with a flat module layout. `definition.yml` uses metadata schema version `1.0.0`; that is separate from the extension version.
