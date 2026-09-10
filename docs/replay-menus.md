# Replay menus and player views

Recordings appear beside existing results in the native single-player Skirmish
battle history. The default ordering is newest saved time first: a named
snapshot uses its save time, and a full recording uses the match-end save time.
The original date heading, sorting controls and scrolling remain in use.
Unnamed recordings keep the map name. Existing game results remain unchanged.

Click once to select a row; click the selected row again to open its native
statistics. A selection outline shows which entry the controls apply to.
Only recordings offer **Rename** (also F2) and the right-pointing **Watch replay**
hand. Statistics screens keep their native navigation and have no replay overlay.

Clicking Watch replay verifies the recording while keeping the history screen
visible. Progress appears there; leaving cancels preparation. Playback starts
only after verification succeeds. A required settings restart is reported
separately and preserves the normal configuration.

During a match, **Escape > Save replay** saves a separately named snapshot while
the full recording continues. The compact name editor has Save and Cancel,
with an inline error only when saving fails. Normal mission exit saves the full
recording. An abrupt crash preserves files but does not guarantee a playable prefix.

During playback, portraits on the left select whose reports/book to inspect.
The tick/status display is always at the top right. F3 adds the saved date,
game and UCP framework versions, and a compact summary of recorded packs.
Full exact settings and asset checks still govern replay admission.
Use the ordinary Escape menu to resume or leave; mission restart is disabled.
The minus/plus buttons and keyboard shortcuts use the native speed handler,
including UCP2-Legacy's installed extended-speed setting. Recorder defines no
independent speed steps or limit. Native speeds from 1100 display as 1000+.
After successful completion, **Statistics** replaces the speed strip and opens
the current recording's existing statistics after the native world-exit cleanup.
Report buttons also remain usable during paused and completed replay playback.

## In-game previews

Captured from the packaged module using the game's German UI. Layout and controls
are shared with the English UI; these are actual game captures, not mockups.

![Native battle history, selection and replay hand](images/replay-history.jpg)

![Player portraits, permanent tick status and F3 details](images/replay-controls.jpg)

## Validation status

0.48.2 completed fresh named and automatic single-player recordings, followed by
a loaded-save continuation from tick 94,548 to 248,979. Snapshot statistics and
return to history were checked in game. The host capture from one physical Steam
match completed offline on the second PC; its client capture also passed on
0.48.0. These results do not cover repeated multiplayer games or connection loss.

0.48.3 removes the native logical-pause rejection specifically for report actions
71..79 during replay. Original-binary branch checks cover both executable variants;
live acceptance of this correction is tracked separately from playback checks.
