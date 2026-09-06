# Multiplayer findings and capture attribution

## First Ascension action run

Two SHC 1.41 clients connected by native TCP/IP on the same PC, using published
recorder 0.19.0, UI 1.0.1, Automarket 1.1.0 and Ascension Multiplayer 1.0.11.
The match used Der Grüne Punkt with two humans, Wolf and Saladin. Both lobby
speed values were verified as 200. This does not validate Steam transport.

The interval from tick 1024 to 16384 lasted about 83 seconds. Both clients logged
the same 63 timed commands in the same order, including 42 building commands,
17 escape commands, one player request and three trades. All 241 resource
checkpoints and all post-command resource snapshots matched.

RNG stream 1's current value/index differed from tick 2816 onward, initially by
one advance. Stream 2 matched. Stream 1 has both local presentation and game
logic callers; these logs do not establish the cause or prove it harmless.
Immediate categories 12 and 117 remained uncovered. Category 12 is also queued
after native world hashing despite its lobby-oriented enum name. The strict
comparator returned incomplete. Do not whitelist these categories from their
names alone, discard RNG1, or interpret equal resources as a full-world checksum.

The user later reported both humans defeated while the AIs continued. Capture
had already sealed. Neither the defeats nor Automarket setting changes/troop
orders were established captured. A longer shared capture window and visible
status are necessary for the next run. Diagnostic traces are not playable replays.

## Attribution in 0.20.0

With multiplayer diagnostics enabled, two checked detours observe entry to
the native RNG methods: SHC `0x46A800`/`0x46A7D0`, Extreme
`0x46AA20`/`0x46A9F0`. They filter ECX to the actual match RNG object, read the
return address from the entry stack and leave original instructions/registers
unchanged. No RNG call is added, suppressed or reseeded. Single-player calls
are ignored. Instrumentation adds overhead and still needs live measurement.

Each checkpoint adds an optional `rngCalls` array of `{stream, returnAddress,
count}` entries since the preceding checkpoint. Counts reset after that row;
the first checkpoint begins the capture and has no preceding interval. At most
512 distinct stream/address pairs are retained per interval; overflow stops
diagnostics with an explicit error rather than silently dropping callers.

Recorder scope gates relocate CALL instructions. The emitter provides an exact
map from the relocated return address to its native equivalent, so the same
audio/UI call can be compared across processes. Other extensions' generated
return addresses remain raw: investigate their code mappings before treating
an address difference as a different caller. Tail calls retain their caller's
return address, so attribution does not uniquely identify the tail-call site.

Version 0.20.0 attempted to retain immediate payloads but read the unused timed
ring payload. Those bytes are invalid evidence. Version 0.21.0 reads the native
fixed buffer at synchrony base + `0x2D834`, with capacity 61,000 bytes. The command
header still comes from the ring. Both local transmission and remote receive-copy
use this separate buffer; the timed replay limit remains 1260 bytes. Headers now
identify corrected evidence with `immediatePayloadSource: native-fixed-v1`.
Immediate events remain gaps. System-message pointer fields are not dereferenced.
Formats 5/6 retain their strict validation semantics; attribution is supplemental.

## Native immediate handlers and synchronization inspection (0.21.0)

The original SHC function table at `0xB38E10` maps command 12 to `0x480B10`
(`CommandCheckSync`). It declares ten bytes and sets scheduled time to zero.
The payload is little-endian signed 16-bit lag, unsigned 32-bit world hash, and
signed 32-bit advertised match tick. Sending selects the local player's fields;
execution selects the resolved protocol invoker. This is active synchronization
traffic. The old category enum's lobby/AIV description is misleading here.

Command 117 maps to `0x4863A0` and transfers 136 bytes: two four-byte parameters
followed by two 64-byte pixel planes. Execution updates the player's face bitmap
and its dirty marker. This explains the observed player-dependent traffic but
does not establish a complete replay strategy for immediate commands or resync.

`--inspect` now includes `nativeSync`. It requires corrected payload headers,
valid ten-byte messages and sender/roster consistency. It compares copies of the
same sender's advertisement by advertised tick, allowing different arrival ticks.
It reports receipt hash differences separately from different players advertising
different world hashes at a common tick. All human slots must be represented in
both files for an all-player hash comparison. Zero hashes and ticks below ten
are excluded from that comparison, following the native check's readiness rules.
Missing advertisements stay visible; conflicting repeats, malformed data, old
payloads and incomplete file sequences produce inspection errors.

Native hashes are partial checksums, not full-world cryptographic evidence. A
match in this supplemental inspection cannot turn incomplete strict comparison
into a pass. Hash generation is spread across native phases; this inspection
does not replace their execution or make multiplayer playback available.

The original-executable tests execute 20 local/remote immediate paths per variant
with the actual Lua payload reader: ring slots 0/199, zero-byte, ten-byte,
136-byte, 1261-byte and 61,000-byte payloads. Transport, memory helper bodies and
a synthetic command callback are stand-ins; native queueing, fixed/ring address
selection, actor translation and dispatch branches run original instructions.
These checks do not exercise the live UCP detour bridge or a Steam connection.

Run `python compare_multiplayer.py A/commands.jsonl B/commands.jsonl --inspect`
to include command/category counts, coverage gaps, resource/command digests and
RNG caller totals even when strict comparison stops at a gap. The exit code and
top-level result still come from strict comparison. Inspection is a summary of
observations, not a second acceptance test. Compare corresponding tick intervals
when investigating individual caller differences; whole-window counts alone do
not identify the first divergent call.

## Menu and verification

The multiplayer pause menu has a native-skinned **Replay status** entry. It
shows waiting/active/saved/failed test capture, commands and uncovered events.
A saved window explicitly says that later actions are no longer captured. With
diagnostics off, it explains that multiplayer replay is unavailable. It does not
offer SP snapshot saving in MP. Back/Escape return to the original pause menu;
keyboard interception in MP is limited to this status dialog.

Automated tests cover status transitions, original menu actions, caller bounds,
relocation mapping, payload capture, failure isolation and inspection after gaps.
Optional original-executable tests execute both native RNG methods at initial
and wraparound indices, with and without the actual Lua observer callback, and
compare the full RNG structure and registers. The UCP detour bridge is a test
stand-in; these tests do not replace a live UI/observer compatibility check.
