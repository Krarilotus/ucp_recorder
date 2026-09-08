# Replay execution boundaries and completion gates

This is the current contract audit, not a claim of complete match equivalence.
Addresses below refer to the checked Crusader and Extreme executables listed in
`code/native.lua`. Original control flow and replay modifications are separated.

## Native phases

```text
Window input / menu / audio / receive
  determine outer-loop budget
  repeat:
    select and execute waiting commands (current clock T)
    processGameTick:
      save/synchronization paths may return early
      conditional clock boundary: observe T, advance RNG/time to T+1
      map/path/view maintenance, including on paused calls
      conditional world updates
    return observer (a function returned; not necessarily a clock step)
    receive / Bink / tactical-powers callback
  render / menus / input
```

| Boundary | Crusader | Extreme | Current replay ownership |
| --- | --- | --- | --- |
| Timed command executor | `4892F0` | `489400` | Original handlers; observe actual actor, payload and execution order |
| Tick function entry | `45CD10` | `45CF20` | Reject stopped or viewer-paused local playback before any tick-owned maintenance; loading and recording retain native admission |
| Pre-clock observer | `45CE44` | `45D054` | Starting snapshot and checkpoint describe state after preceding commands, before the next clock advancement |
| Clock increment | `45CE58` | `45D068` | Native increment, conditional on menu/pause state |
| Tick early-return epilogue | `45CDA8` | `45CFB8` | A halt detected by the pre-clock callback returns here immediately |
| Main-loop return observer | `57C384` | `57C7B4` | Completes a pending MP tick frame only if its clock advanced exactly once |

The pre-clock observer is not the entry to `processGameTick`. Other native
callers include map preparation and editor/UI code. Loading is excluded by the
session lifecycle; a caller returning without visiting the observer does not
create a tick-journal frame. These distinctions matter for paused commands and
replacement-world loading.

Commands executed before the initial snapshot are already reflected in that
world and are not replayed again. After activation, command stream order is the
order of native execution, not network receipt. The ending checkpoint currently
describes the last observed **pre-clock** boundary, after its preceding commands;
the following clock step is outside that prefix.

Native command construction chooses the larger of the match clock and
synchrony's local clock, then adds command delay. Its selector accepts due
commands without consulting logical pause. Acceptance of user input while
paused therefore does not by itself prove immediate execution. Playback's
**viewer** pause stops the selector before it consumes the saved stream; this
is independent of record-time paused inputs.

## Paused viewing and stopped playback

Space selects flat view in the original window handler. A completed height/view
refresh (`501A20` / `501DA0`) sets the same flag that permits world updates during
map rotation. Original `processGameTick` can therefore run world-update callees
while its clock remains unchanged. A paused function call is not necessarily a
simulation no-op.

The existing `pause` and `pausedCamera` gates remove the two pause bypasses for
the local replay profile. They remain inactive in live multiplayer. The new halt
guard has a different responsibility: once a replay finishes or fails, even
tick-owned maintenance must stop. The old halt target merely skipped the clock
increment, leaving maintenance reachable. Paused calls could miss that hook
altogether. Entry/epilogue guards now cover both cases. Ordinary recording has
no halt flag; an inactive scope remains inactive even with an offline identity.

The original-code check runs both tick implementations, including the real
256-height refresh and its flag write. Other subsystem callees are stand-ins.
It verifies unchanged live-MP control flow, paused refresh without clock
advancement, local pause gating, immediate endpoint exit, later paused entry,
sync/save returns and stack preservation. It does **not** certify render/input
callbacks outside this function as non-mutating.

### Navigation proves maintenance is gameplay state

`updateSeparateAreaTileMap` (`4995E0` / `499750`) decrements its refresh countdown
on each call, even if the match clock did not advance. On expiry it resets to
200; when marked dirty, it rebuilds connectivity regions and building linkage.
The countdown is at `117CAD8` / `120F718`. These are observed native writes,
not suggested restore values. Crusader saves the countdown in section 1023.

In Crusader, `canUnitReachAdjacentTile` (`4105F0`) reads the connectivity region
of the unit and neighboring tiles and passes those regions to the navigation
query from the unit-controls UI. `canNavigateToDefensiveBuilding` (`40AC80`)
also consumes the layer from `UpdateLord` (`56C8A1` / `56D0E9`); its result
controls the lord's state and target writes.
Consequently, advancing this maintenance schedule during a viewer pause is not
equivalent to only redrawing the screen.

Playback now blocks the whole tick at entry while logically paused or in a
halting menu, using the same native menu query as command selection. The session
arms this rule after snapshot restoration and clears it before exit/replacement;
map preparation still receives its native calls. This adds no per-tick Lua call
and does not write individual navigation fields. Existing endpoint guards retain
priority, including after the viewer presses unpause.

Original-code checks execute the real countdown decrement, expiry/reset and
clean-map return in both variants. They reproduce the old paused write and check
the new admission rule, recording/loading pass-through, disabled scope and live
MP behavior. The flood fill and other maintenance owners remain outside that
check. A paused view refresh now waits for resume inside this tick owner; live
inspection of flat view, reports and camera behavior is still required.

**Record-time pause is a separate open contract.** Two command selections can
share a match-clock value with maintenance between them. A timestamp-only stream
cannot describe that ordering. Freezing a viewer must not erase source events:
before changing the journal, trace source selection/maintenance boundaries and
their consumers. Do not normalize this by resetting a countdown or changing the
live game's pause rules. This finding does not attribute either archived RNG
failure to navigation.

The existing optional `singleplayerRngDiagnostics` now samples this countdown
at restoration/capture start and each RNG checkpoint. Its existing main-loop
return hook also counts returns, returns without clock advancement and clock
jumps, without adding a hook or flushing a file per return. These counters do
not assert that maintenance was admitted: a viewer-paused call returns at entry.
`tools/inspect_replay.py compare` reports the first differing countdown and return
pattern separately from RNG attribution. This can expose an earlier state
difference without declaring a viewer pause itself to be desynchronization.

For the next targeted SP check, enable those diagnostics **before recording**:

1. Record a short fresh match with an AI and a few building/unit orders, without
   pausing. End the mission and replay it once untouched.
2. Replay that same recording again. Pause for 30 seconds, inspect the book,
   toggle flat view, then resume to the recorded endpoint. Note any blocked
   inspection or visual refresh that fails to recover after resume.
3. Make a separate short recording with two orders given during a pause,
   separated by ten seconds. Resume, end the mission and replay it untouched.

Compare each playback with its own source attribution file. Step 2 isolates
viewer control; step 3 investigates missing source phases. Preserve the entire
replay folder and each attempt's logs, including a failed attempt. These are
new-candidate recordings; do not edit historical environment manifests to load
an older recording under different code.

## Restore coverage

| Domain | Current mechanism | Remaining proof obligation |
| --- | --- | --- |
| Saved native world/header | Original container reader, native preparation, second extension-aware read | Equivalence after the complete outer handler, including caches and repeated extension callbacks |
| RNG | Full initial state; SP checks; MP pre/post boundary observations | MP RNG1 consumers/effects between observations, including final-boundary input, are not fully classified |
| Human/AI identity | Explicit offline roster and synthetic human handles | Full AI match and clean repeat/exit in a real process |
| Command queues | Original scheduler/handlers, explicit recorded order | Pending commands at snapshot start and multiple selection batches sharing one clock value |
| Automarket | Explicit persisted state and original synchronized actions | End-to-end loaded/recovered match outcome |
| Other extension state/assets | Exact config/package files and configured paths | Private-state ownership; asset discovery is not a complete effective-namespace model |
| Replacement worlds | Linked segments and prepared native saves | Authoritative completion of replacement and safety of the outer caller at transition |

The native loader resets saved scheduling counters during preparation. Reapplying
saved sections addresses that observed write, but neither a successful decode nor
that correction proves the cause of the missing spawn. Keep the 18,112 and 22,912
failures separate until matching execution evidence establishes their causes.

## Gates still open

1. Classify simulation-relevant writes between the boundaries above. Prove
   whether multiple paused command batches need an explicit phase identity;
   do not simply remove the current 100-command-per-tick rejection.
2. Compare relevant state after the complete load, before its first consumer.
   Identify the missing spawn's unit/caller, differing decision and first writer.
3. Complete repeated SP playback, then independent host/client offline playback,
   each against its own source and declared endpoint. MP playback remains local.
4. Verify replacement/recovery, required extension state, read-only inspection,
   Extreme and the remaining localized UI on the packaged candidate.

Keep historical manifests and packages unchanged. Structural preflight admits
a playback attempt; only a completed attempt verifies the checked endpoint.
Missing continuations remain incomplete prefixes. Portable tests, original-code
checks and installed-game results must be reported separately.
