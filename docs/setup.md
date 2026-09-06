# Install a recorder test release

Use a separate copy of your installed game and a working UCP3 installation.
Keep your usual game and replays. This build targets original Crusader HD 1.41
and Crusader Extreme 1.41, not Definitive Edition. Both variants have code ports;
latest-build live verification is outstanding. Multiplayer playback is unavailable.

## Download and install

1. Open the PR you want to test in
   [Corax34/ucp_recorder](https://github.com/Corax34/ucp_recorder/pulls). Find its
   **test release** link in the comments. Assets are published in
   [Krarilotus/ucp_recorder releases](https://github.com/Krarilotus/ucp_recorder/releases),
   so the upstream Releases page may be empty.
2. Choose the release for that PR's current commit: tags look like
   `pr-<number>-<commit>`. Under **Assets**, download **`recorder-0.28.0.zip`**
   and optionally its `.zip.sha256` checksum. **Source code (zip)** and
   **Code > Download ZIP** are repository archives, not installable modules.
3. Close the test game. Use the UCP launcher's extension install **+** button/file
   picker to select the ZIP. If selecting it from Downloads fails, copy it into
   your test game folder and select it there.
4. For manual installation, put the ZIP at
   `<test game>/ucp/modules/recorder-0.28.0.zip`. Keep it zipped. This is a
   **module**, not a plugin; `definition.yml` and `init.lua` are at the ZIP root.
5. Reload the extension list, enable **UCP-Recorder**, and select **0.28.0**.
   Older packages may remain for old replays, but the active configuration must
   select the intended version once. Update any preset requiring an older recorder.
6. PR builds are unsigned development packages. Use the launcher's **Disable
   Security** option for this isolated test configuration if UCP rejects the
   package as unsigned. Do not alter Windows security or antivirus settings.
7. Keep your working graphics configuration, including **graphicsApiReplacer**
   and its dependencies if needed. Recorder does not replace a graphics wrapper.
8. Launch through UCP. Check the console/log says
   `enabling extension: recorder version: 0.28.0`. Since 0.26.0,
   `<test game>/ucp/recorder-startup.txt` records the versions/order that reached
   recorder and its startup result.

Do not change `meta.version` to the recorder version. `meta.version: 1.0.0` is
the definition file format; `version: 0.28.0` is the extension version, and
`name: recorder` determines the ZIP filename.

Releases appear after verification and publication succeed. The publisher runs
on PR updates where installed, with scheduled backfill on the publishing fork.
If a PR has no release, check its workflow result; do not rename a source ZIP
to imitate a release. Each release identifies its source commit.

## Ascension and Automarket

Install Ascension and its dependencies through the store/launcher as usual.
Recorder does not bundle or install them. The combination under investigation is:

| Extension | Version / requirement |
| --- | --- |
| recorder | 0.28.0 for this PR |
| Ascension-Multiplayer | 1.0.11 |
| automarket | 1.1.0; the adapter checks this exact wire format |
| protocol | 1.0.0 for the Automarket adapter |
| map-extensions | 1.0.0 for the Automarket custom save section |
| ucp2-legacy | 2.15.1 with its dependencies |
| ui | 1.0.1 in the prepared Ascension test setup |
| steam-multiplayer | 1.2.3 in the prepared test setup |

This is a test configuration, not complete compatibility certification. A
different UI version is not automatically the cause of a startup failure.
Other custom protocols are not supported for replay.

Keep dependencies before consumers. In the resolved extension order,
**protocol, map-extensions, ui and automarket must be enabled before recorder**.
Putting recorder after Ascension and its dependencies is the simple arrangement.
Check the startup report's ordered list; installing the ZIPs alone is insufficient.

Automarket's weekly trades run as simulation work. Recorder captures its settings
commits and custom starting-save section; it must not inject weekly trades twice.
See [adapter details](automarket-replay.md).

## First five-minute check

1. Start a **new single-player Skirmish**, with an AI and **Auto: on** in the lobby.
   Do this before multiplayer diagnostics.
2. Place a building and issue a troop order. With Automarket enabled, set a buy
   or sell threshold and commit it, then let several weeks pass.
3. Open **Pause > Save replay as...**, enter a name, and continue playing so you
   can distinguish this shorter copy from the full recording.
4. Use **Quit Mission** to finalize the recording automatically. Killing the
   process does not finalize it. Native game saves/loads during capture are
   unsupported; the recorder's named-copy action is separate.
5. Return to **Skirmish > Replays**. Play both the named copy and full recording;
   check that the shorter copy ends earlier.

Each session has its own folder under `<test game>/ucp/replays/`. Named copies
preserve recording in the background; duplicate display names cannot overwrite
sessions. In multiplayer the pause-menu item is **Replay status**; diagnostic
captures are not playable replays and have no named-replay save action.

To check recorded settings, change an ordinary gameplay option after recording
and relaunch. Select the recording and click **Play**. If a restart is requested,
exit normally and let the helper reopen the game. Return to the library and click
Play on the selected recording. Recorded extension versions must remain installed;
the helper does not download them. Your normal configuration is preserved.
This path has automated parser/helper tests but still needs live verification.
See [recorded settings](recorded-settings.md).

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| `Recorder session hook conflicts at save` with 0.17.0 | Install this PR's ZIP and select its version. 0.17.0 rejected map-extensions 1.0.0's CALL save wrapper; 0.18.0 fixed it on both variants. Switching executables does not update the module. |
| A hook conflict with the current version | Preserve the guard. Send the startup report and `ucp3.log`; addresses and expected/found bytes help identify a different patch. Do not NOP the check or remove map-extensions from an Automarket game. |
| Recorder missing from the list | Check `ucp/modules`, the exact `recorder-<version>.zip` name and root-level `definition.yml`. Reload the list and use the published asset. |
| `Could not find a matching extension` | Install the named version, or update the active preset's requirement. `Replay-Ascension-Test` is a separate local preset, not a recorder dependency; it is unnecessary for this manual setup. |
| `Enable recorder after protocol` or unavailable Automarket protocol | Correct the active order so the adapter's dependencies and Automarket are enabled first. |
| `Replay option requires a finite number` | The message names the option path. Replace NaN/infinity with a deliberate valid value in the test configuration; recorder does not choose gameplay values for you. |
| `UCP cannot restore these replay option values without changes` | Preserve the configuration and report it. The installed framework would change an option's type/value on reload, so recorder refuses an inaccurate restore. |
| No startup report | The launcher may have failed before recorder enabled, or writing failed. Send `ucp3.log` and the launcher error. Recorder also prints the report to the console/log when it runs. |
| Missing replay buttons | Confirm the loaded version/startup result, then use a single-player Skirmish lobby. In a recorded match, open the pause menu. Report a screenshot, resolution and variant. |
| Settings restart fails | Read `ucp/replays/restart-error.txt`. Confirm the recorded versions are installed and exit normally when requested. |
| Capture/playback fails later | Preserve the session folder, including `manifest.json`, `last-error.txt` or `desync.json` if present, and `ucp3.log`. Failed/cancelled captures cannot be played. |

Before relaunching, copy **`ucp/recorder-startup.txt`** and **`ucp3.log`**: a new
launch can overwrite them. The startup report lists extensions, stages and errors,
not option values. `READY` confirms initialization, not successful replay testing.

Include the PR/release link, loaded recorder version, Crusader or Extreme, when
the failure happened and the shortest reproduction steps. Attach both logs and
the relevant replay folder. Review files before public sharing: logs and replay
configurations can contain local paths and your settings.

For two-PC tests, complete the single-player check on each PC, then follow the
[multiplayer diagnostic instructions](multiplayer-diagnostics.md). Use the same
versions, options and capture window. Diagnostic comparison does not establish
that multiplayer playback is ready.
