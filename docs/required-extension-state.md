# Required extension simulation state

Map Extensions 1.1.0 providers can opt into required-state API version 1. Recorder
adds their read-only capture to its existing `extensions.zip`, authenticated by
the existing native SHA256 implementation. The normal world restore invokes the
save owner's validators before extension deserialization. No alternative native
save or network command path is introduced.

Each existing 64-tick checkpoint includes the provider's format, package SHA256
and deterministic state digest. Preflight rejects missing or incompatible
contracts; playback compares the digest at the original checkpoint boundary.
`tools/compare_multiplayer.py` also compares these fields between physical peers.
The digest is supplied by the simulation owner; Recorder does not scan its units
or recreate its RNG. Native-only recordings without providers retain their old
checkpoint shape and behavior.

The recorder also observes required state at each recorded boundary and seals
`finalExtensionState` into SP and multiplayer replay manifests. Playback compares
it at the exact ending tick, including endings between 64-tick checkpoints.
The save owner permits paired observation/digest callbacks; AIC Tactics uses a
fixed native memcpy snapshot and hashes it only when sealing/copying a recording.
This avoids full state hashing every tick and retains the ending observation even
when quit/recovery has already changed the live world. Snapshot and recorder
overhead still need measured game acceptance.

Protocol 1.1.0 retains the existing Automarket 1.1.0 command layout. The adapter
admits that version without changing recorded command IDs or payload validation.
Multiplayer captures record the admission protocol registration; a delayed
80-byte lobby request/reply is classified as transport only for that exact ID,
version and fixed header. Protocol's owner ignores it outside the lobby. Unknown
custom messages remain unsupported; no admission message is replayed as a timed
simulation command. This avoids a harmless late reply forcing a recovery segment.

This integration does not establish a lobby content handshake or prove replay
compatibility by itself. Validation must include native-only
recordings, required-state captures, save/reload and recovery segments, differing
provider content, physical peers and measured checkpoint cost. No such acceptance
is claimed by these source changes.
