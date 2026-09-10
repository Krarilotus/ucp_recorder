# Replay seeking (0.50.1 preview)

This branch adds a clickable progress bar beside the persistent tick counter.
It is not the published 0.49.4 build. Native restoration and capture latency
still require acceptance testing before this feature is released.

## Storage and playback

Single-player and multiplayer recording write an additional restore point every
25 elapsed game years. Each multiplayer peer owns its own points; playback is
always offline. Offline playback creates a local point every elapsed game year.
The native calendar, measured from the recording's starting date, drives both
schedules; a loaded game does not immediately save decades of duplicate points.
Capture waits for an idle command boundary. A calendar jump produces one point
for the current world rather than copies for dates that were never observed.

Embedded points live in the replay's `snapshots` directory and accompany named
copies. Local points live in `ucp/replay-cache`, remain available after playback
finishes, and are removed when the viewer closes. They are never copied into a
shared recording. The active viewer reserves space before capture and evicts old
local points to stay within 256 MiB. Locked files stop further cache creation
rather than cause repeated unbounded writes. On its first capture, each process
reclaims orphaned cache files under an exclusive native file lease. A running
process keeps its lease until exit, so another instance cannot remove its points.
The OS releases the lease after a crash; cleanup never enumerates replay folders.
Each concurrently running viewer has its own 256 MiB budget.

Snapshots use the game's existing PKWARE-compressed save format. No new runtime
codec, shell process or Python dependency is introduced. Each point also carries
the complete 40,016-byte RNG block and small stream-position metadata. The
measured 1,213,093-byte native save would add roughly 15 MB for twelve points over
300 years, including RNG blocks. This is an example, not an eight-player bound;
the earlier 200 KB snapshot target was not met by measured recompression.

Clicking the bar restores the closest earlier usable point and executes the
remaining recorded inputs. This is not reverse simulation or an instantaneous
jump to every tick. Ordinary native/UCP speed controls still own the speed.
Playing seeks resume when they reach the target; paused or completed playback
seeks stop there. A completed replay can be revisited without leaving the viewer.
The bar and counter refresh at most four times per second.

## Ownership and invariants

- `snapshot-cadence` handles calendar deadlines only.
- `snapshot-store` publishes native worlds and RNG sidecars, checks their hashes,
  and copies embedded points. Optional damaged points do not invalidate a named
  replay copy. Simulation mutation during capture remains a hard failure.
- `replay-streams` bookmarks byte offsets and prefetched command/maintenance
  records. Binary I/O is essential: Windows CRT text cookies can change when
  sealing trims the stream suffix. Both LF and existing CRLF records remain valid.
- `replay-snapshots` schedules captures at the pre-clock boundary, after recorded
  maintenance. It queues seeks from UI input and loads only after input dispatch.
  `Session:startPlayback` remains the sole owner of native load, extension state,
  RNG restoration, command execution counts, and offline roster reconstruction.
- `replay-timeline` maps the complete prepared recovery chain to elapsed ticks.
  Segment identity disambiguates a native clock that moves backwards after sync.
  Transitioning between segments retains earlier local points.
- `native-ui` calculates click offsets from the same native rectangles used for
  hit testing. The HUD has no separate resolution-dependent mouse transform.

Restore preparation validates point metadata, stream bounds and world/RNG hashes
before releasing the running world. If an optional point is unavailable, it
rechecks the original starting save. If that is also damaged, it cancels the seek
and retains the active replay. Commands and determinism checks remain enabled
after restoration. Stopping at a paused target happens before consuming its
multiplayer tick frame, so unpausing cannot leave an unmatched pending frame.

Periodic snapshots in both singleplayer and multiplayer use `world-capture.freeze`:
it copies the checked 122-section world and registered extension state at one
simulation boundary. `codec-worker` runs the original PKWARE compressor in one
native thread against those private buffers. It never calls Lua, reads live game
state, or invokes native save/transport routines. `snapshot-jobs` polls completion
without waiting, then publishes the native container and RNG sidecar. Capture
waits during synchronization and pending command execution. `multiplayer-snapshots` converts trace positions into
replay byte bookmarks during the existing journal scan, and preserves the
25-year cadence through recovery. Named prefixes copy only included points.

Only one world may be in flight per game process: approximately 28 MiB for SHC or
50 MiB for Extreme, in addition to the disk cache budget. Closing or seeking
cancels that optional point; memory is released only after the worker exits.
Pending points are not included in a named copy or a sealed recording. The next
job waits rather than building an unbounded queue. Freeze and final container
publication still run on the game thread; separate timings expose their cost.
Measured 0.50.0 native yearly saves blocked Extreme playback for 547–922 ms.
The new path needs live timing and restore-equivalence acceptance before release.

The release encoder retains native status, bounds and checksum handling, but
omits the diagnostic conversion's immediate decode-and-compare pass. Background
snapshot compression uses the original codec in both profiles. Native tests
independently decode both build profiles and frozen snapshots. Preparing a recovery chain validates
each segment once and retains its small RNG block; subsequent transitions reuse
that admission instead of rescanning all commands and assets. Native starting
files are still hash-checked before replacing an active world.

## Remaining completion gates

1. Compare continuous playback with repeated native restore-and-continue runs,
   including recorded maintenance, command boundaries, loaded-save starts,
   extension state, player statistics, completion-to-backward seeks and recovery.
2. Measure native capture and restore stalls in representative saves before
   release. Timing is logged at each point; no sub-100 ms claim has been verified.
3. Publish/install a distinct verified preview, then provide one complete
   single-player acceptance sequence before requesting further multiplayer tests.

Offline regression coverage includes calendar scheduling, binary bookmarks
through sealing, prefetched commands, corruption/fallback, atomic publication,
failed eviction, crash cleanup/lease exclusion, native mouse coordinates, and
recovery-chain clock resets. The lease test uses actual Windows file sharing.
These tests establish orchestration and checked native boundaries, not full
simulation equivalence or rendered menu appearance.
