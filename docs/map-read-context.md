# Shared native filename binding

Recorder 0.50.32 consumes Map Extensions 1.1.4's filename binding instead of
resolving the resource manager and getter again inside Map's reader. Map needs
the same read context to distinguish fresh maps from saves with missing required
state; a game tick is insufficient because maps can contain editor ticks.

`code/native-save.lua` validates the owner's context capability, pointers and
20-byte getter description. `code/load-sites.lua` verifies those bytes before
Recorder installs its existing scoped filename override. Map calls the shared
entry, so Recorder snapshot paths retain their existing lifecycle. There are no
new scans, hooks, file formats or per-tick operations. Discovery still uses the
cached `core.AOBScan` already shipped in UCP 3.0.7.

This depends on the Map owner correction and Recorder's earlier state-capability
PR. Portable tests cover relocated owner metadata, missing capabilities, changed
getter bytes and retained wrapped save/load callbacks. Native image checks and
installed playback acceptance are recorded separately in the PR.
