# UCP Recorder

Work in progress: recording and playback of single-player Stronghold Crusader and Crusader Extreme Skirmishes using UCP3.

Version 0.24.0 captures the game's completed multiplayer world-hash subtotals
and compares them by match tick. `--inspect` now identifies differing simulation
domains while retaining uncovered-command and RNG evidence. This is an opt-in
diagnostic addition; multiplayer playback is still unavailable. See
[native world-hash evidence](docs/native-world-hashes.md).

Version 0.23.0 isolates a wall-clock-triggered AI taunt RNG advance and checks
exact native command payload lengths, including Extreme's larger selection
packet. **Make fresh recordings:** this uses simulation profile `recorder-sp-v9`;
older captures require their earlier release. See [taunt and command-layout
findings](docs/taunts-and-command-layouts.md). Chat playback is not included.

Version 0.17.0 records new single-player Skirmishes automatically, saves them on normal mission exit, and adds **Save replay as...** to the in-game pause menu. Named copies preserve the match so far while recording continues. The lobby has **Auto: on/off** and **Replays** buttons; the library supports naming and automatically chooses the recorded-settings restart when Play needs it. Buttons use the game's original interface skin, gold font and red modal frames.

Development 0.18.0 Crusader playback completed twice with two AIs. A separate Automarket match replayed 69,573 ticks and 13 commands with RNG/resource checkpoints matched; native named-save controls were also exercised. A published 0.19.0 two-peer Ascension test captured 63 identical timed commands and 241 matching resource checkpoints, but RNG stream 1 differed and immediate messages left coverage incomplete. **Extreme gameplay, settings restart and full multiplayer replay still need live verification and engineering.** Multiplayer recording/playback remains unsupported. See the [library flow](docs/replay-library.md), [dispatch evidence](docs/replay-dispatch.md) and [multiplayer findings](docs/multiplayer-findings.md).

Automarket 1.1.0 has an experimental replay adapter for its settings commits and native custom save section. Use protocol 1.0.0 and map-extensions 1.0.0, with **recorder after protocol in the extension order**. The normal weekly trades run in the simulation; they are not replayed as extra trades. Other custom protocols remain unsupported. See [Automarket replay notes](docs/automarket-replay.md).

Optional **Multiplayer diagnostics** logs actual command execution and periodic simulation evidence for comparing two peers. Version 0.19.0 adds shared start/end ticks so logs can finish before either player disconnects. Diagnostics are disabled by default and do not enable multiplayer replay. See [multiplayer trace instructions](docs/multiplayer-diagnostics.md) and the [harder test matrix](docs/multiplayer-test-matrix.md).

Version 0.20.0 adds **Replay status** to the multiplayer pause menu, including
whether test capture is active, saved or failed. Captures include RNG caller
counts and immediate-message payloads for investigation. The comparison tool's
`--inspect` option summarizes this evidence without relaxing its pass criteria.
Version 0.22.0 rejects accidental same-player comparisons and adds RNG caller
differences by checkpoint interval to `--inspect`. These observations can locate
where to investigate; they do not establish a desync cause or a replay pass.
See [paired capture analysis](docs/multiplayer-comparison.md) for interpretation.
Version 0.21.0 corrects the immediate-message payload buffer and decodes native
synchronization hash advertisements. Discard immediate payload bytes collected
by 0.20.0; the timed-command and resource evidence is unaffected by this fix.

## Testing this build

Use a separate game installation with UCP3 developer mode and this module enabled. If your game needs Graphics API Replacer, keep it and its dependencies enabled in the test configuration.

1. Open a single-player Skirmish lobby and configure the match. **Auto: on** is the default; click it to disable recording for this game launch.
2. Start the match. Recording begins automatically, including its starting save, RNG state and UCP settings.
3. Optionally open the pause menu and choose **Save replay as...**. Type a name and save a completed copy up to the latest recorded boundary. The full-match recording continues.
4. Leave through **Quit Mission** to save the full recording automatically. Do not terminate the process to finish a replay.
5. Return to a Skirmish lobby, open **Replays**, select a completed session and click **Play**. Use **Rename replay...** to label a completed recording.
6. If settings differ, Play queues a settings restart. Exit normally; the helper reopens the same executable with the recorded UCP configuration. Open **Skirmish > Replays** again; the requested recording is selected. Click **Play**.

Do not delete older recordings to make a new one: every session has a separate folder under `ucp/replays/`. A settings restart leaves your normal `ucp-config.yml` intact. It requires the recorded extension versions to be installed; it does not download dependencies. If the helper fails, inspect `ucp/replays/restart-error.txt`.

On failure, inspect `ucp3.log` and the session's `last-error.txt` or `desync.json`. A failed or cancelled capture cannot be played. Native game saving/loading during a recording is currently unsupported and fails the capture explicitly. The recorder's **Save replay as...** action copies replay files without issuing a native save command.

See [session format and limitations](docs/replay-sessions.md), [browser and restart testing](docs/replay-browser.md), [native port notes](docs/native-port.md) and [changelog](CHANGELOG.md).

## Development

```sh
python -m pip install lupa==2.6 unicorn==2.1.4 capstone==5.0.7
python -m unittest discover -s tests -v
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME"
python tools/build.py
```

The builder creates `dist/recorder-0.24.0.zip` with a flat module layout. `definition.yml` uses metadata schema version `1.0.0`; that is separate from the extension version.
