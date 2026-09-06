# Native world-hash observations

Recorder 0.24.0 adds read-only completed-hash evidence to opt-in multiplayer
diagnostics. Enable the existing shared capture window on both peers and run:

```sh
python tools/compare_multiplayer.py HOST/commands.jsonl PEER/commands.jsonl --inspect
```

`worldHashes` is supplemental evidence. The strict comparison still checks
timed commands, RNG and resources and keeps exit codes 0/1/2. Inspect the world
hash report as well: its agreement cannot turn uncovered immediate commands into
a replay pass, and its disagreement is an additional reason to investigate.
No multiplayer playback support is enabled by this release.

## Capture point and native layout

The original `recomputeHashesAndSendResync` starts at SHC `0x48CC90` and Extreme
`0x48CDA0`. It skips calculation while halted or while its countdown is nonzero.
The observer runs at `0x48DA2E` / `0x48DB3E`, just after the final subtotal has
been added to the local total. The checked detour retains the complete four-byte
`CMP` and seven-byte `LEA`; ESI still identifies the synchrony object here.

Relative to that object, local-player slot `p` uses:

| Field | Offset |
| --- | --- |
| Total | `0x7A898 + p * 4` |
| Advertised match tick | `0x7A8BC + p * 4` |
| Subtotal `i`, zero-based 0 through 13 | `0x7A8E0 + p * 48 + i * 4` |

**Fourteen values use a twelve-value stride in the original binaries.** The last
two values overlap the next slot's first two values. Slot eight reaches version
slots zero and one at `0x7AA90` / `0x7AA94`. This finding is not a recorder patch
to the game's layout, nor proof of the earlier RNG divergence. Reading another
peer's table later cannot recover an authoritative set of fourteen subtotals.

The observer copies the local completed set immediately, normalizes signed
reads to unsigned 32-bit values and verifies the modulo-2^32 sum against the
native total. It never invokes recomputation, consumes RNG, sends commands or
changes the native table. Single-player and other receiver objects are filtered.

The domains, in native order, are units, buildings, trees, tribes, player data,
map state (section 1023 and additional AIV data), tile map, entities, moats,
climb data, pitch ditches, unused/zero, AIVs and heat maps. These names describe
native subtotal groups; they do not claim every byte of game state is covered.
The native routine temporarily excludes selected transient fields before hashing
and restores them. A raw unit-buffer or process-memory hash is not equivalent.
No complete RNG dependency audit has been established, so RNG checks remain.

## Interpreting the report

Each checkpoint carries up to 256 completed observations since the previous
checkpoint. Each includes local player, advertised tick, total and 14 copied
subtotals. Empty intervals are valid: the native countdown can skip calculation.
The header marker `native-domains-v1` identifies this capture method.

- `pairedTicks` / `sameTicks` / `differentTicks` count shared advertised ticks.
  Peers need not calculate on every identical tick. Zero pairs is no evidence
  of agreement.
- `firstDifference` names differing domains even if two changes cancel in the
  summed total. The result includes both local-player identities.
- `leftUnpairedTicks` / `rightUnpairedTicks` expose nonoverlapping observations.
- Identical repeated samples at one tick are counted as duplicates. Conflicting
  samples at the same tick fail inspection; no arbitrary last value is selected.

The reader validates the entire sequence, periodic boundaries, peer/window
identity, sample timeline, unsigned values, sums and footer. Missing arrays,
unflushed samples, malformed or interrupted captures and roster/resync changes
return `inspectionError` without partial comparison counts. RNG caller attribution
is not required for this independent analysis. Immediate-message coverage gaps
can coexist with the report and remain gaps in the strict comparison.

The ending checkpoint seals the configured window. A computation occurring later
at that same tick is outside the sealed observation and will not be included.
Unbounded capture stopped between checkpoints exposes a nonzero
`pendingNativeHashes` footer count instead of claiming those samples were saved.

## Validation and limits

`tests/check_world_hash_native.py`, invoked by `tests/check_executables.py`, runs
the complete original recomputation on both game variants with and without the
actual Lua observer and subtotal reader. It covers all eight local slots, native
halt/countdown skips, exact store offsets, unsigned sums, register/stack behavior
both command-12 send/no-send branches and subsequent overlapping writes. The detour's original instructions execute
from a separate trampoline. Native writes and final registers must agree.

The hash callee returns deterministic test data; the queue callee and UCP callback
bridge are stand-ins. The test does not validate the hash algorithm, installed framework
bridge, transport timing or gameplay determinism. Lua fixtures cover capture
failure, bounds, reset and isolation; paired-file tests cover corrupt/ambiguous
evidence and total collisions. Fresh live Ascension/Steam captures remain needed.
