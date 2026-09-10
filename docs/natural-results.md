# Natural match results during replay

A 0.34.0 untouched Crusader/Ascension recording ended at tick 96,631.
Playback matched all 1,502 checkpoints through 96,128, including optional spawn
context, then entered native results at 96,134. Returning to the lobby correctly
reported **interrupted**, not finished. No player commands were involved.

The native `RenderInGameWinDefeatWindowDisplayElement` (SHC `0x004AFB30`)
compares `timeGetTime() - gameOverTime` against 8,000 milliseconds. When the
unsigned elapsed time exceeds that value, it switches to menu 29 (victory) or
30 (defeat). Simulation continues behind the banner until that render-driven
transition. Thus recording and playback can stop at different simulation ticks
even with identical simulation state.

Version 0.35.0 holds only that transition during playback. A separately owned
session flag changes the comparison flags at SHC `0x004AFB4A` / Extreme
`0x004AFCBA`, taking the existing unsigned-below-or-equal branch. Both the
five-byte comparison and following two-byte branch are checked before installing
the gate. The existing native emitter preserves registers and stack; its game
mode guard restricts the change to single-player modes 0 and 99. There is no
change to the game's victory logic, game-over timestamp, recording behavior,
multiplayer behavior or simulation profile.

The replay's recorded endpoint still requires all commands to execute and the
final resource state and full RNG state to match. Paused, failed and finished
playback keep the native banner and remain inspectable until the viewer exits.
Reset releases the timer gate before returning to normal play.

Native executable checks exercise original and patched victory/defeat branches
for both games, including the 8,000/8,001 ms boundary, inactive replay scope,
and multiplayer exclusion. The menu-switch callee is a stand-in; those checks
do not establish successful in-game replay completion by themselves. Later live
checks include completed SHC single-player, loaded-save and offline multiplayer
playback, plus an Extreme match through tick 36,598 with five commands on 0.48.3.
All recorded RNG and resource checkpoints matched in those runs. Repeated live
multiplayer games and recovery remain separate acceptance gates.

## Recording completion and native history ownership

The observed Extreme match entered results but stayed marked `recording` until
Leave. Its replay duration consequently included minutes spent looking at the
statistics. Views 29 and 30 are the native victory/defeat result transitions
(`MenuViewType` in OpenSHC); they also serve historical result browsing. The
recorder therefore seals only an active recording/capture at this transition,
from its last observed simulation boundary. Loading and playback are excluded.
No victory logic, render timer or simulation state is changed.

The native `StoreGameIntoSKMasters` (SHC `0x4d52a0`, Extreme `0x4d5630`)
packs the result and inserts it by score into the game's maximum 250 records.
At SHC `0x4d534d` / Extreme `0x4d56dd`, the full record has just been copied
and EBX still holds its insertion index. A checked, read-only detour links that
exact record's hash to the just-completed replay. A rejected low-scoring result
never reaches this point. Pending identity is discarded on another menu view.
The history presentation merges one explicitly linked native entry; it never
writes or deletes the game's persistent history. Matching dates/names alone
cannot merge old matches. Removing a replay reveals its native entry again.

`tests/check_match_results_native.py` executes the original insertion, shifting
and rejection code with the packer and disk writer substituted. Unit tests
cover lifecycle exclusions and preservation of even identical old records.
Live validation of the 0.48.4 result transition is still required.
