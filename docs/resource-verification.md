# Resource verification (0.8.0)

Command execution and RNG equality can miss an incorrect trade or resource refund. Capture now snapshots the 25 signed resource integers of each real player (slots 1..8), including gold, and compares those integers during replay. Slot 0, UI buffers, padding and unrelated structure fields are excluded. No native hash function or RNG call is invoked by the observer.

Automarket 1.1.0's `ui/market/init.lua` derives the resource base from the native resource-reset instruction and uses a player stride of 0x39f4. Original executable checks confirm the operand at Crusader 0x40c334 references 0x115c2c8, and Extreme 0x40c344 references 0x11eef08. The same 25-slot layout and stride apply to both profiles. The observer reads these addresses; it does not patch the reset function.

The manifest stores the starting and final arrays. Each 64-tick checkpoint includes an array alongside its RNG values. Before playback starts, malformed or missing arrays fail preflight; after native loading, the actual resources must match the starting array. During playback the first mismatch writes desync.json with the tick, phase, player, zero-based resource ID and expected/actual amounts, then halts the session. Completion between checkpoint ticks still checks the final array.

Tests cover all eight player strides in both profiles, signed values, detached snapshots, incorrect gold with matching RNG, the last resource of player 8, starting-save mismatch and missing/malformed stream evidence. All native operand checks are read-only. Full match playback and Automarket credit/refund behaviour remain live-test requirements. Unit/building state and private extension state are still outside this check.
