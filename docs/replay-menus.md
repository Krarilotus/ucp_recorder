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

## Validation status

The recent native-history entry/return and ordinary recording Escape fixes were
exercised live. The latest selection, hand, HUD/render-pass, date and preparation
changes pass portable regression checks and original SHC/Extreme hook checks;
their final appearance still needs an in-game check. Both a named snapshot and
its full source reproducibly stop at RNG divergence tick 27072. Multiplayer
host/client offline playback is not yet signed off.
