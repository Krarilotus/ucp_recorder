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

This integration does not establish a lobby content handshake or prove replay
compatibility by itself. A non-checkpoint ending boundary still requires a final
state comparison in acceptance testing. Validation must include native-only
recordings, required-state captures, save/reload and recovery segments, differing
provider content, physical peers and measured checkpoint cost. No such acceptance
is claimed by these source changes.
