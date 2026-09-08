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
do not establish successful in-game replay completion. Separate RNG2 missing
unit-spawn failures remain under investigation, and multiplayer captures remain
diagnostic-only.
