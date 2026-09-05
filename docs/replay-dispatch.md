# Replay dispatch and queue recovery (0.16.0)

A recording stores the order in which native command handlers actually returned.
Playback must preserve that order even though its queue is populated at different
times and ring positions from the original match. This stage connects admission,
selection, native execution checks and cancellation as one playback pipeline.

## Native evidence

The original WinMain loop calls `processWaitingCommands`, then `processGameTick`,
then `receiveAllTransmittedCommands` on each inner iteration. Crusader call sites
are `0x57C375`, `0x57C37F` and `0x57C389`. There are also receive calls outside
this inner loop. The prior receive hook was therefore not simply once per frame;
this change binds admission directly to selection instead of relying on receive
call placement or prefetching 64 ticks of commands.

`getCommandIDFromCommandSelectionStuff` (Crusader `0x480440`, Extreme `0x480610`)
scans physical ring positions upward from its scan index, takes at most 100 due
entries and stably sorts that batch by translated player slot. In single-player,
the translator returns the local player for every sender. Equal-player entries
therefore retain physical scan order, not their enqueue order.

For example, enqueue command A at slot 199 and command B at slot 0 for the same
tick with scan index 0. The native selector chooses B before A. A recorded stream
need not use the same ring positions on playback, so native selection alone
cannot reproduce its recorded execution sequence. The original-binary harness
reproduces this ordering in both games; this is not merely a model prediction.

The new selection hook covers the complete five-byte prologue
`PUSH ECX; PUSH EBX; PUSH ESI; MOV ESI,ECX`. Its caller tests EAX immediately
after returning and retains the synchrony receiver in ESI. The hook uses the
existing UCP thiscall wrapper, while the original dispatcher and command handlers
remain responsible for execution and native actor resolution.

| Native state relative to synchrony receiver | Crusader | Extreme |
| --- | --- | --- |
| Write cursor | `0x109EE0` | `0x166370` |
| Selected pairs (ring slot, logical player), 100 entries | `0x109EEC` | `0x16637C` |
| Selected count | `0x10A20C` | `0x16669C` |
| Ring, 200 entries of 1,272 bytes | `0x3C67C` | `0x3C67C` |

## Playback behavior

1. The selector hook clears the selected count and asks the session to enqueue
   only commands due at the current tick. Future commands stay in the stream;
   a late command or lack of room fails playback before dispatch.
2. Each enqueue must reach the expected copy boundary with the expected source
   and length, advance the write cursor exactly once, and leave a pending entry
   with the expected tick, sender, category and bytes. Only then does the journal
   take ownership of the slot.
3. The journal builds the due batch in recorded sequence. All entries are checked
   before publishing the selected array. An unknown pending native entry fails
   the whole selection instead of allowing a partially checked batch to run.
4. The original native dispatcher resolves actors and calls handlers. Existing
   pre/post hooks still verify ownership/content and count returned executions.
5. On failure or cancellation, replay-owned pending slots are marked processed
   and the selected count is cleared. A failed enqueue restores the previous
   slot bytes, write cursor and saved command scratch. This does not undo an
   arbitrary side effect inside a faulty native or extension handler; playback
   remains stopped after such a failure.

Only single-player playback uses this selector. Recording, idle play, native
loading and all multiplayer modes use the original selector. Error/finished
playback cannot publish another batch. Abort cleanup also refuses to write while
in multiplayer. The local spectator/player identity is not replaced globally.

The supported batch limit is 100 commands at one execution tick. The native
limit is per invocation, so a paused game could theoretically dispatch multiple
batches without advancing its tick. The current stream does not identify those
separate phases. Recording and preflight reject that case rather than inventing
a new execution timeline; the limit is not a claim that such native play is
impossible. The SP profile advances to `recorder-sp-v8`.

## Verification

The portable suite exercises real Lua session feeding, selection and completion
for 1,600 commands with 1, 3 and 20 simulated ticks per frame. No receive callbacks
are needed. Additional cases cover ring wrap, future/late commands, complete-batch
rejection, partial enqueue recovery, invalid ring states, cancellation, stale
playback in multiplayer and the preflight batch limit.

Run `tests/check_executables.py GAME_DIRECTORY` with lupa, Unicorn and Capstone
installed for the original-binary checks. `check_dispatch_native.py` loads the
original scheduler, selector, player translator and dispatcher into an isolated
Unicorn address space and connects their memory to the actual Lua replay engine.
It reproduces the native A/B reversal, verifies 600 ordered dispatches per
variant through repeated ring wraps, checks actor/tick/stack/saved registers and
tests restoration after an actual native enqueue encounters a length mismatch.

The emulation uses stand-ins for UCP callbacks, memory helpers and a four-byte
test command handler. It does not prove the real UCP bridge, arbitrary game
handlers, audio timing, UI rendering or full-world replay correctness. No new
live playback is claimed by these results. Original executable identities are
the same verified 1.41 variants listed in [the native port notes](native-port.md).

## Multiplayer snapshot boundary still required

The command-order work is useful groundwork but does not make an MP save a
single-player replay. Native `writeMapOrSaveFile` (`0x474480`) updates elapsed
game-duration state and calls `sendPeriodicSyncMessages` every tenth serialized
section in multiplayer. A local call is therefore not a passive synchronized
snapshot. The normal SP load path also reconstructs local network identity.

MP playback still needs a coordinated snapshot/offline-load design, mode and
actor semantics, immediate/system-event replay, resync and extension-state
coverage. This PR does not enable MP playback or silently apply the SP simulation
profile to multiplayer recordings. See [network coverage](multiplayer-diagnostics.md).
