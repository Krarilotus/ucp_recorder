# UCP Recorder

Work in progress: recording and playback of single-player Stronghold Crusader and Crusader Extreme Skirmishes using UCP3.

Version 0.3.0 adds individual replay sessions, starting saves and settings snapshots. **The new save/load playback path still needs end-to-end in-game verification.** Multiplayer is not supported yet.

## Testing this build

Use a separate game installation with UCP3 developer mode and this module enabled. If your game needs Graphics API Replacer, keep it and its dependencies enabled in the test configuration.

1. Open a single-player Skirmish lobby and configure the match.
2. Enable the right-hand recorder checkbox near the bottom. This arms a new recording; clicking it again cancels.
3. Start the match. The module captures the starting save and begins recording.
4. Leave through **Quit Mission** to finalize the recording. Do not terminate the process to finish a replay.
5. Return to a Skirmish lobby with the same active UCP settings. The left-hand playback checkbox loads the latest completed session for the current game variant. The saved starting state replaces manual map/AI setup.

These remain temporary checkbox controls. A labelled replay browser follows in the next stage. Do not delete older recordings to make a new one: every session has a separate folder under `ucp/replays/`.

On failure, inspect `ucp3.log` and the session's `last-error.txt` or `desync.json`. A failed or cancelled capture cannot be played. Saving/loading during a recording is currently unsupported and fails the capture explicitly.

See [session format and limitations](docs/replay-sessions.md), [native port notes](docs/native-port.md) and [changelog](CHANGELOG.md).

## Development

```sh
python -m pip install lupa==2.6
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-0.3.0.zip` with a flat module layout. `definition.yml` uses metadata schema version `1.0.0`; that is separate from the extension version.
