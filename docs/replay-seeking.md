# Replay seeking (development branch)

This branch adds a clickable progress bar beside the persistent tick counter.
It is not the published 0.49.4 build. Native restoration and capture latency
still require acceptance testing before this feature is released.

## Storage and playback

Single-player recording writes an additional restore point every 25 elapsed
game years. Offline playback creates a local point every elapsed game year.
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

The native save writer updates presentation duration and, in multiplayer mode,
periodically calls transport synchronization. Capture restores duration; the
scoped offline save gate suppresses the transport call without changing actual
simulation mode. Original SHC and Extreme branch/ABI tests cover that guard.
Live multiplayer saving remains prohibited by this provider.

## Remaining completion gates

1. Implement embedded 25-year points for live multiplayer capture through its
   read-only world owner, including journal-to-replay bookmark conversion. The
   single-player writer must not be enabled against live network state.
2. Compare continuous playback with repeated native restore-and-continue runs,
   including recorded maintenance, command boundaries, loaded-save starts,
   extension state, player statistics, completion-to-backward seeks and recovery.
3. Measure native capture and restore stalls in representative saves before
   release. Timing is logged at each point; no sub-100 ms claim has been verified.
4. Publish/install a distinct verified preview, then provide one complete
   single-player acceptance sequence before requesting further multiplayer tests.

Offline regression coverage includes calendar scheduling, binary bookmarks
through sealing, prefetched commands, corruption/fallback, atomic publication,
failed eviction, crash cleanup/lease exclusion, native mouse coordinates, and
recovery-chain clock resets. The lease test uses actual Windows file sharing.
These tests establish orchestration and checked native boundaries, not full
simulation equivalence or rendered menu appearance.
