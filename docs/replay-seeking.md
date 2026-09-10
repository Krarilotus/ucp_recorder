# Seeking: feasibility and restoration ownership

Backward seeking is possible in principle, including after verified completion.
It is not implemented by the current progress bar. Simulation cannot run in
reverse: restore an earlier world, then execute the recorded inputs up to the
chosen boundary. Existing verification checkpoints contain hashes, not worlds.

The existing starting save provides one restore point without increasing replay
size. `Session:startPlayback` already owns native load, RNG restoration, stream
initialization, admission checks and offline multiplayer roster restoration.
A small-file seek implementation should reuse that path, then stop at a verified
pre-clock boundary. It must keep ordinary command execution and determinism
checks enabled. Replaying forward may remain slow for long matches at native
maximum speed; seeking backward does not avoid this cost.

Fast seeking would require additional restorable snapshots. One current loaded
save is 1,213,093 bytes; additional DEFLATE compression yielded 837,471 bytes at
level 6 and 833,020 at level 9. This sample does not meet the proposed 200 KB
budget. It does not prove a specialized delta format impossible, but such a
format adds dependencies between snapshots and a new validation/restore path.

Before shipping a seek control:

1. Queue loading at the existing menu-update boundary, after input dispatch has
   returned. Preserve player-view selection and clear old stream prefetch,
   command queues, pause/halt flags and any outstanding multiplayer tick.
2. Restore through the extension-aware native loader. A mid-replay snapshot
   also needs RNG, extension save sections, command/checkpoint/tick/maintenance
   stream positions, execution counts and the correct recovery segment.
3. Pause at the target pre-clock boundary without consuming its commands twice
   or advancing one extra tick. Retain viewer-pause maintenance protection.
4. Verify start/end seeks, repeated backward seeks, pause and speed changes,
   failed restoration, and offline playback across multiplayer recovery segments.
   Compare the reached state against continuous playback before claiming success.

The current release adds no periodic snapshots or irreversible input shortcuts.
The choice between slower reload-and-simulate seeking and larger fast-seek
snapshots is a product tradeoff, not a claim that seeking is technically excluded.
