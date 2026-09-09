# Replay browser and settings restart (0.17.0)

For new 0.25.0 recordings, the helper uses `replay-config.yml`, a profile with
exact loaded versions and resolved options. See [recorded launch settings](recorded-settings.md).
The raw `ucp-config.yml` path below describes legacy recordings.

The separate recorder browser has been replaced by the native battle history.
See [menu controls](replay-menus.md) for current selection, statistics, naming and
playback behavior. `battle-history.lua` owns the merged catalogue;
`history-native.lua` adapts native navigation and data pointers. The preparation
controller verifies recorded settings and streams before native loading.

## Restart handoff

**Play**, when the recorded settings differ, validates the selected session and starts a hidden Windows PowerShell helper. It does not terminate the game. The user exits normally; the helper waits for that process and then starts the same executable with `--ucp-config-file=".../ucp-config.yml"`. The recorded file is passed directly to UCP rather than copied over the user's normal configuration.

The helper verifies the executable hash, process identity and settings hash. A changed file prevents launch and produces `ucp/replays/restart-error.txt`. It passes `UCP_RECORDER_REPLAY` only through the child environment, allowing the browser to select the requested recording after restart. The user enters Skirmish and clicks Play; playback is not injected into an uncertain startup stage.

The helper runs with the current user's rights. JSON data is never evaluated as PowerShell, game arguments are quoted, process handles are closed, and Win32 process/path calls use Unicode. No dependency installation or download occurs. The recorded module versions must be available already; the next game launch still performs normal UCP loading and compatibility checks.

Tests execute the actual helper with `Get-Process` and `Start-Process` replaced by fakes, while keeping its real JSON, path and hash checks. They start no game. Real process handoff and graphics initialization after restart remain pending integration tests.

## Live test checklist

1. Verify the always-visible native button skins/outlines, the pause-menu Save replay action, keyboard naming/cancel/confirmation, and labels, modal placement, row text, selection, empty/error lists and all buttons at minimum and normal display resolutions in both variants.
2. Start a short match with default recording enabled, save a named copy while continuing, change speed, pause/resume, issue several commands, quit the mission and replay it through completion.
3. Replay a second time and choose an older recording; verify that no command/RNG cache survives.
4. Change UCP settings, queue a restart, exit normally and verify the matching recording loads with the stored settings. Check that the default configuration bytes are unchanged.
5. Repeat with Graphics API Replacer enabled and inspect errors without assuming a process launch proves renderer success.
6. Exercise in-game quit/restart/load, save/autosave rejection and attempted spectator actions; inspect completion status and the first divergence report.

See [automatic recording and naming](replay-library.md) for the current flow and native evidence.
