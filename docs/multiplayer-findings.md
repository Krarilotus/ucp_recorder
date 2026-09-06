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

Immediate-command gaps now retain the declared payload (bounded to 1260 bytes)
and sender handle. They remain gaps: their effects, transport phases and replay
semantics are not implemented. System-message pointer fields are not dereferenced.
Formats 5/6 retain their strict validation semantics; attribution is supplemental.

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
