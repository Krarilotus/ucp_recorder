# Install a recorder test release

Use a separate copy of your installed game and a working UCP3 installation.
Keep your usual game and replays. This build targets original Crusader HD 1.41
and Crusader Extreme 1.41, not Definitive Edition. Both variants have code ports;
latest-build live verification is ongoing. Multiplayer recordings are intended
for offline playback through the single-player replay browser; multiplayer
equivalence is still being verified.

## Download and install

When **UCP-Recorder 0.49.1** is available in the UCP3 `3.0.7` extension store,
install it there together with its dependencies. Store publication signs the
package through UCP's normal pipeline; the unsigned-PR instructions below are
only for manual preview downloads. If using UCP2-Legacy, select **2.15.2** as
described below. UI **1.0.1** is a required dependency for this release.

Store integration is a testing rollout, not a claim of complete multiplayer
recovery support. Archive identities can differ between store and PR builds;
keep the exact installed ZIP with your recordings.

Ordinary testing uses the release ZIP. The separate diagnostic bundle contains
an inner module ZIP for targeted investigations; see [build profiles](build-profiles.md).
Install one build at a time and retain its artifact with your recordings.

1. Open the PR you want to test in
   [Corax34/ucp_recorder](https://github.com/Corax34/ucp_recorder/pulls). Find its
   **test release** link in its description or comments. Assets are published in
   [Krarilotus/ucp_recorder releases](https://github.com/Krarilotus/ucp_recorder/releases),
   so the upstream Releases page may be empty.
2. Choose the release for that PR's current commit: tags look like
   `pr-<number>-<commit>`. Under **Assets**, download **`recorder-<version>.zip`**
   and optionally its `.zip.sha256` checksum. Replace `<version>` with the version shown on that release. **Source code (zip)** and
   **Code > Download ZIP** are repository archives, not installable modules.
3. Close the test game. Use the UCP launcher's extension install **+** button/file
   picker to select the ZIP. If selecting it from Downloads fails, copy it into
   your test game folder and select it there.
4. For manual installation, put the ZIP at
   `<test game>/ucp/modules/recorder-<version>.zip`. Keep it zipped. This is a
   **module**, not a plugin; `definition.yml` and `init.lua` are at the ZIP root.
5. Reload the extension list, enable **UCP-Recorder**, and select **the downloaded version**.
   Older packages may remain for old replays, but the active configuration must
   select the intended version once. Update any preset requiring an older recorder.
6. PR builds are unsigned development packages. Use the launcher's **Disable
   Security** option for this isolated test configuration if UCP rejects the
   package as unsigned. Do not alter Windows security or antivirus settings.
7. Keep your working graphics configuration, including **graphicsApiReplacer**
   and its dependencies if needed. Recorder does not replace a graphics wrapper.
8. Launch through UCP. Check the console/log says
   `enabling extension: recorder version: <version>`. Since 0.26.0,
   `<test game>/ucp/recorder-startup.txt` records the versions/order that reached
   recorder and its startup result.

Do not change `meta.version` to the recorder version. `meta.version: 1.0.0` is
the definition file format; `version: <version>` is the extension version, and
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
| recorder | The selected PR release version |
| Ascension-Multiplayer | 1.0.11 |
| automarket | 1.1.0; the adapter checks this exact wire format |
| protocol | 1.0.0 for the Automarket adapter |
| map-extensions | 1.0.0 for Automarket and UCP2 custom save sections |
| ucp2-legacy | 2.15.2 with saved simulation state and its dependencies |
| ui | 1.0.1 in the prepared Ascension test setup |
| steam-multiplayer | 1.2.3 in the prepared test setup |

If the store still offers UCP2-Legacy 2.15.1, use the saved-state
[2.15.2 test release](https://github.com/Krarilotus/extension-ucp2-legacy/releases/tag/test-fbb634bb2331)
from [its PR](https://github.com/UnofficialCrusaderPatch/extension-ucp2-legacy/pull/6).
Likewise, if UI 1.0.1 is absent from the store, install the
[UI 1.0.1 test release](https://github.com/Krarilotus/ucp-extension-ui/releases/tag/test-d3a807cfee70)
from [the menu-array fix](https://github.com/gynt/ucp-extension-ui/pull/6).

**Update UCP2-Legacy before recording with 0.45.0.** Version 2.15.1 leaves the AI
attack target cycle outside saved worlds. This can desync playback even with
identical RNG and no player commands. UCP2-Legacy 2.15.2 saves that state through
map-extensions; install both, reload the launcher, and choose 2.15.2 in the active
configuration. Record a new match. Older recordings do not contain the missing
state; changing their version or settings metadata does not recover it.

This is a test configuration, not complete compatibility certification. A
different UI version is not automatically the cause of a startup failure.
Other custom protocols are not supported for replay. See the
[source audit and compatibility boundaries](extension-compatibility.md).

Keep dependencies before consumers. In the resolved extension order,
**protocol, map-extensions, ui and automarket must be enabled before recorder**.
Putting recorder after Ascension and its dependencies is the simple arrangement.
Check the startup report's ordered list; installing the ZIPs alone is insufficient.

Automarket's weekly trades run as simulation work. Recorder captures its settings
commits and custom starting-save section; it must not inject weekly trades twice.
See [adapter details](automarket-replay.md).

## First five-minute check

1. Start a **new single-player Skirmish**, with an AI and automatic recording enabled in the launcher.
   Do this before multiplayer diagnostics.
2. Place a building and issue a troop order. With Automarket enabled, set a buy
   or sell threshold and commit it, then let several weeks pass.
3. Open **Pause > Save replay**, enter a name, and continue playing so you
   can distinguish this shorter copy from the full recording.
4. Use **Quit Mission** to finalize the recording automatically. Killing the
   process does not finalize it. The recorder's named-copy action is separate
   from saving a native game. Since 0.40.0, loading a saved single-player Skirmish
   closes the previous recording and automatically begins a new one after loading.
5. Return to **Skirmish > Battle history**. Select a recording and click the right
   hand to play both the named copy and full recording;
   check that the shorter copy ends earlier.
6. During playback try portrait selection, the speed keys/buttons and F3. At
   completion click **Statistics** and check it shows that recording's results.

Each session has its own folder under `<test game>/ucp/replays/`. Named copies
preserve recording in the background; duplicate display names cannot overwrite
sessions. In multiplayer use **Replay status > Save capture as...** to name a
copy of the capture so far. The full capture continues until mission exit.
New multiplayer recordings also live under `ucp/replays` and can be selected
for local single-player playback. Older captures in `ucp/multiplayer-recordings`
lack the required tick data. The 0.42.0 playback/recovery path is experimental;
see [current validation and recovery behavior](offline-multiplayer.md).

To check recorded settings, change an ordinary gameplay option after recording
and relaunch. Select the recording and click **Play**. If a restart is requested,
exit normally and let the helper reopen the game. Return to the library and click
Play on the selected recording. Recorded extension versions must remain installed;
the helper does not download them. Your normal configuration is preserved.
Since 0.39.0, missing or unreadable exact versions are shown before a restart is
queued. Clicking Play displays the full list, also saved as
`ucp/replays/requirements.txt`. Install those versions using the launcher's
extension list, or install their original release ZIPs using **+**. A newer
version does not replace the required one. If the required version is no longer
available from the store or its original releases, this replay cannot be played
on that installation. Recorder does not claim that a missing local version has
also disappeared from the internet.

If the framework or packages change while the helper waits for game exit, it
shows a Windows error dialog and saves `ucp/replays/restart-error.txt`. Restore
the listed requirements and try again. A present package still passes through
UCP's normal format and security checks on launch.
This path has automated parser/helper tests but still needs live verification.
See [recorded settings](recorded-settings.md).

## Recording after loading a saved Skirmish

With **Auto: on**, load the save normally. Recording starts at the loaded game's
first simulation boundary, using its actual tick, full RNG state and current
UCP configuration. The next mission exit seals that recording; named copies
continue to preserve the full recording in the background. Repeated loads
produce separate recordings, even when loading an earlier point in the match.
The recorder's own replay load does not create another recording.

The original `.sav` file does not contain a complete historical UCP profile.
Recorder therefore stores the settings actually active when you load it; it
cannot recover unknown settings used before that save existed. Use the correct
modules when loading your save, just as you would without Recorder.

This path currently covers saved **single-player Skirmishes**. Campaigns, map
editor sessions, and multiplayer restoration/playback need separate work. The
native reader's completion marker is not a replacement for save-file validation:
Crusader itself does not report every corrupt-read or decompression failure.

For the next in-game check, load a saved Skirmish, issue a troop order and change
production, save a named replay copy, then continue and quit the mission. Play
both recordings. Repeat with another save in the same game process and verify
that the two loaded matches appear separately. Add Automarket threshold changes
when using Ascension. Crusader and Extreme both need this live check.

## Troubleshooting

| Symptom | Next action |
| --- | --- |
| `Recorder session hook conflicts at save` with 0.17.0 | Install this PR's ZIP and select its version. 0.17.0 rejected map-extensions 1.0.0's CALL save wrapper; 0.18.0 fixed it on both variants. Switching executables does not update the module. |
| `Native hashing requires binary string writes` with 0.43.1 | Install 0.43.2 or newer and select that version. Older UCP 3.0.7 runtimes truncate binary string writes; the recorder now uses the compatible byte API. Restart before recording. |
| `Asset file escaped its parent` with 0.43.2 and configured UCP aliases | Install 0.43.3 or newer and restart. UCP returns versioned directory entries for unversioned or wildcard aliases; recorder now resolves the parent through the same API. |
| `DISABLED` in the startup report | Recorder failed a check before installing its hooks. UCP displays a message and lets the game continue **without recording**. Correct the reported conflict/order and restart. |
| A hook conflict with the current version | Preserve the guard. Send the startup report and `ucp3.log`; addresses and expected/found bytes help identify a different patch. Do not NOP the check or remove map-extensions from an Automarket game. |
| Recorder missing from the list | Check `ucp/modules`, the exact `recorder-<version>.zip` name and root-level `definition.yml`. Reload the list and use the published asset. |
| `Could not find a matching extension` | Install the named version, or update the active preset's requirement. `Replay-Ascension-Test` is a separate local preset, not a recorder dependency; it is unnecessary for this manual setup. |
| `Enable recorder after protocol` or unavailable Automarket protocol | Correct the active order so the adapter's dependencies and Automarket are enabled first. |
| `Replay option requires a finite number` | The message names the option path. Replace NaN/infinity with a deliberate valid value in the test configuration; recorder does not choose gameplay values for you. |
| `UCP cannot restore these replay option values without changes` | Preserve the configuration and report it. The installed framework would change an option's type/value on reload, so recorder refuses an inaccurate restore. |
| `FAILED: hook and menu installation` | Installation had already started. The game must not continue with partial patches; correct the error and restart. |
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
