# Comparing two multiplayer captures

Run the packaged offline tool on one trace from each player:

```text
python tools/compare_multiplayer.py HOST/commands.jsonl PEER/commands.jsonl --inspect
```

The strict result uses exit code **0 matched**, **1 different**, or **2 incomplete**.
An uncovered immediate/system command still makes it incomplete. Supplemental
observations never change that result. A matched diagnostic window is not proof
that a complete multiplayer replay can be reconstructed.

## Select independent peers

Both headers must identify different logical human player slots, the same game
variant/executable, starting boundary, format and resolved environment. Formats
with network context also require the same game mode and logical roster. Their
transport handles and command-ring slots may differ: those are local identities.
Version 0.22.0 rejects a copied trace or two captures from the same player instead
of treating them as corroborating evidence. Older files without player identity
must be recaptured; the tool does not infer a player from a filename.

The environment hash currently covers resolved configuration, extension load
order and versions, and framework version text. It does not hash every loaded
extension file or external asset. Keep both test installations on the verified
same package; an unchanged version number cannot establish identical code.

## RNG interval observations

`rngIntervals` requires the caller attribution added in recorder 0.20.0. It reads
both complete evidence streams, checks every 64-tick checkpoint and pairs only
aligned boundaries. The first checkpoint's caller counters are excluded because
the observer did not cover a complete preceding interval. Its RNG/resource state
can still be compared as the starting observation.

- `firstStateDifference` gives the first observed differing RNG values/indexes,
  full RNG hash or player resources.
- `firstCallerDifference` gives the preceding and ending ticks of the first
  interval with different invocation counts, with each stream, return address
  and the two counts. The interval runs after the earlier checkpoint through the
  later checkpoint; it does not identify the exact tick of each call.
- `callersWithDifferences` retains how many intervals differed as well as the
  total right-minus-left count. Opposite differences in successive intervals do
  not erase the evidence merely because their total is zero.
- `unpairedCheckpoints` identifies an extra tail in an unbounded capture. A
  bounded capture must include its declared ending checkpoint on both peers.

Immediate-command gaps can coexist with these observations. Missing counters,
duplicate caller entries, invalid states, missing sequence numbers, malformed
footers and data after completion produce an inspection error. Roster changes
and native resynchronization transitions also stop interval analysis because the
original peer/state association no longer describes the whole window.

Different caller counts do **not** establish causality. A call may be a consequence
of an earlier divergence or presentation work. Equal counts do not prove equal
call order, arguments or consumed values. Return addresses belong to the recorded
variant; investigate them in the matching executable. Known recorder-relocated
calls are mapped back to their native return address by the capture hook. Other
extensions' generated code can still have process-specific addresses.

`nativeSync` separately compares the game's advertised command-12 world hashes.
It requires the corrected fixed-buffer payload source from 0.21.0. The game's
partial world hash and the recorder's RNG/resource observations cover different
state; neither substitutes for a complete reconstructed multiplayer replay.
