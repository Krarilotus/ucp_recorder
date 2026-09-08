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
| Tick function entry | `45CD10` | `45CF20` | Halt guard rejects stopped local replays before any tick-owned maintenance |
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
