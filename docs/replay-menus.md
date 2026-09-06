# Replay menus and player views

## Library

Open **Single Player > Skirmish > Replays**. **Auto: on** records new Skirmishes
and **Quit Mission** seals the full recording. A named copy made during the
match is labeled **Snapshot**; the automatic source is **Full match**. Returning
to the library after finishing selects the full source recording once. Later
visits preserve your selection.

| Action | Mouse | Keyboard |
| --- | --- | --- |
| Select | Click a row | Up / Down; Home / End |
| Play | Double-click the selected row, or Play | Enter |
| Rename | Rename replay... | F2 |
| Remove from library | Remove, then confirm | Delete, then confirm |
| Change page | Page arrows, when present | Page Up / Page Down |
| Return | Back | Escape |

Unavailable actions use the original game's gray disabled text. Canceling a
rename preserves the name. Display names are still ASCII and remain metadata;
they never become paths. Duplicate names do not overwrite another recording.

Removal moves the entire folder, including snapshots, settings and diagnostic
files, into `ucp/replays/removed/REPLAY_ID`. It does not permanently delete them.
An active recording/copy cannot be removed. Existing removed copies cannot be
overwritten, and their IDs are reserved when creating another recording.
To restore a removed recording, close the game and move that folder back one
level into `ucp/replays`, provided no folder with its ID already exists.

## Viewing players

During playback, open **Pause > Replay controls > View player**, select an
occupied player slot, then resume. The native gold, popularity, population and
report rendering use that player's view. The recorded player is selected when
a new replay starts. The selector is unavailable during normal recording,
loading, or multiplayer.

The view is temporary around rendering only. Input, command ownership, replay
manifest and simulation remain tied to the original recording. The ordinary
book and inspection inputs remain available; this does not grant commands to
the viewed player or change fog of war/camera position. Some report navigation
may still depend on the recorded player's native input context; report-by-report
live testing remains necessary.

Failed playback remains failed after a view change. The existing command barrier
blocks live simulation commands, but the separate audit of apparent/ghost
building previews is not complete. Do not treat this selector as proof that all
spectator inputs are harmless.

## Language

English and German are included. With a launcher that supplies
`UCP_GUI_LANGUAGE`, the replay interface follows the UCP language selection.
The companion change is [UCP3-GUI PR376](https://github.com/UnofficialCrusaderPatch/UCP3-GUI/pull/376).
Older launchers and direct game launches fall back to the installed game's
language. Other languages currently fall back to English; diagnostic details
from the engine can also remain English.

Translations are UTF-8 in source and converted to the game's Windows-1252
German glyphs for native drawing. Existing game language files are not replaced.

## Design choices and verification

| Element | Choice and reason |
| --- | --- |
| Buttons | Native pause font 18, centered labels, original colors/blending, tiled skin and disabled style. Native width measurement prevents labels overflowing. |
| Titles | Larger native font 16 and centered text; retain the game's red modal frame and background. |
| Rows | Left-aligned names, duration and Full match/Snapshot status, with a selection border. No repeated Selected footer. |
| Double-click | Play, following the original native load-list's same-row 500 ms behavior. Rename stays explicit/F2 to avoid unexpectedly editing when loading. |
| Navigation | Mouse/keyboard selection; no separate up/down selection buttons. Page arrows exist only for additional pages. |
| Refresh | Refresh on opening and after edits/removal; no redundant Refresh button. |
| Removal | A useful library action, with confirmation and recoverable files. |
| Player selector | Occupied slots only, replay-only, presentation scope; no simulation ownership transfer. |

Native references checked against SHC and Extreme include
`OptionsMenu_Buttons` (SHC `0x00491840`), text width (`0x00471690` /
`0x004718B0`) and the player summary (`0x00433780` / `0x004339C0`). The native
menu dispatcher uses action 0 for input, 1/3 for rendering and 2 for reset; only
rendering is scoped to the viewed player. The gold/popularity strip is outside
that dispatcher and has its own rendering wrapper.

Original-binary tests run the full player-summary function for all eight slots,
with zero/negative and large statistics. Only the pixel/number drawing callees
are stand-ins. They verify selected values, stack/callee-saved registers,
unchanged player/RNG data and restored identity. Portable tests cover keyboard
flow, localization, disabled actions, geometry, nested/error restoration and
recoverable removal. These checks do not replace live visual and full replay
tests.

For live verification, make a fresh recording under this version with RNG
diagnostics enabled. Exercise the library, native book/report tabs and each
occupied view; replay with a different inspection history. Check completion
reports, not just whether playback appears to run. The older 0.29.0 regression
should continue to be reproduced with its exact original settings separately.
