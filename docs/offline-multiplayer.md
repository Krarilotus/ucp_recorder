# Local playback of multiplayer recordings

Version 0.42.0 connects the captured world to the single-player replay library.
Both host and client recordings use the same playback path. No network session,
remote peer or synchronized spectator is involved during playback.

## Ownership

- `multiplayer-capture` observes live commands, native tick boundaries and roster/
  synchronization transitions. It does not inject commands or change live RNG.
- `multiplayer-session` validates and normalizes the journal, and prepares native
  saves for the recovery chain while still in the Skirmish browser.
- `offline-runtime` supplies synthetic handles for recorded humans and retains
  the recorded native multiplayer mode. The original actor translator,
  scheduler and dispatcher continue to own command execution.
- `offline-sites` gates transport, network waiting and pacing during local replay.
  Outside that scope the original instructions run. Multiplayer gameplay rules
  are not replaced with single-player rules.
- `native-snapshots` retains the native UI/map load path and reapplies saved
  sections through the extension-aware FilePackager after map preparation.
  `prepareMap` otherwise resets serialized simulation state, including the
  section 1024 load-balancing counter. Recovery loads use browser context to
  avoid its negative-pause sentinel executing an unclocked gameplay update.
- `session-recorder` owns lifecycle, command feeding and completion; `replay-streams`
  owns files/prefetch. The old prototype hooks and independent RNG path are removed.

The native load-preparation analysis identifies a real state difference, but
has not yet proved the cause of the older tick 22,912/18,112 RNG2 failures.

## Randomness

Each native simulation tick has a 28-byte journal frame with its tick and before/
after RNG values and indices. Commands retain their own before/after states.
RNG1 is presentation-coupled in the original game, including music selection.
Offline playback supplies its recorded input at those boundaries and checks both
streams immediately afterward. RNG2 is checked, never corrected. The existing
full RNG and resource checkpoints remain additional checks.

This does not claim that every presentation dependency is covered. A difference
inside a native tick or command stops playback and must be investigated.

## Recovery and persistence

Synchronization/roster changes, unknown immediate events and clock rewinds end
the preceding playable interval at its last observed boundary. At the next
stable simulation boundary, capture starts a linked segment from the new world.
Raw network events remain available for diagnosis; they are not injected into
an offline transport. Only validated synchronization/portrait traffic (native
categories 12 and 117) is omitted without requiring a replacement world.

The browser presents a chain as one recording. A named copy includes independent
copies of its preceding segments. Removing the automatic source therefore does
not break the named copy. Removal archives all linked segments together and
rolls back earlier moves if a later move fails.

A missing/unfinished continuation leaves the verified prefix available and
playback reports that it ended before an unavailable recovery segment. A damaged
or incompatible prepared segment is rejected before initial loading. Limits:
32 segments per prepared/copied chain, 256 MiB command journal and 128 MiB tick
journal per segment, plus the original native save payload limit. Power loss and
forced process termination are not guaranteed to produce sealed recordings.

## Validation status

Original SHC/Extreme instruction checks cover passive/active transport gates,
ABI preservation, native human translation and 1,200 offline command dispatches
per executable. Lua file tests cover both peers, prefix copies, recovery chains,
framing/hash rejection and unchanged capture-side game memory. Native codec/
FilePackager checks restore all 122 section destinations from prepared captures.

These checks simulate OS/UI boundaries and do not constitute a completed live
multiplayer replay. Required next validation: fresh host/client recordings with
Ascension/Automarket and AIs; local playback on each PC; a loaded save; controlled
disconnect/resynchronization; pause/speed/player inspection; then Extreme.
