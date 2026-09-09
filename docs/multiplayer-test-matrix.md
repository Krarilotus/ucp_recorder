# Multiplayer validation matrix

This is a test plan, not a claim of completed multiplayer replay. Capture and
single-player playback of both peers' recordings are implemented, including
replacement-world recovery intervals; see [ownership and limits](offline-multiplayer.md).
Independent host/client completion and controlled connection recovery remain
live acceptance gates. Playback never requires a multiplayer session.

## Baseline and reproducible collection

Use isolated game directories, the same exact published recorder build and
identical resolved UCP settings on both peers. Keep Graphics API Replacer where
needed. Automarket requires protocol 1.0.0, map-extensions 1.0.0 and recorder
after protocol; its menu dependency needs the UI 1.0.1 bounds fix when testing
the known UI 1.0.0 startup crash. Preserve both configurations, executable/module
hashes, logs and trace folders.

Use two human slots plus two AIs, with enough separation and alliances to let
both players build and issue commands. Let the tester choose the map layout.
For the Ascension acceptance run, use the usual Steam connection with distinct
licensed accounts and speed100 through the native menu. Test native TCP/IP as
a separate transport case. A same-PC pair is
useful for command and ownership comparisons, but does not establish behavior
over a remote network or through Steam. Separate client processes still need
independent game state; a launcher-only single-instance workaround must stay in
the test installation and leave the network implementation unchanged.

For optional transport diagnosis, use a bounded trace such as ticks 1024 through 8192, increasing the end in
multiples of 64 for long games. Wait for each client to seal its own trace before
leaving. Never infer completion from elapsed wall-clock time: lag or pause may
prevent the game from reaching the boundary. Compare the files with the shipped
`tools/compare_multiplayer.py`; save its JSON output beside the originals.
This bounded observer comparison does not replace replay acceptance: each PC
must retain its own full capture and named snapshot, then play them to their
recorded endpoints offline, with all available checkpoints matching.

| Scenario | Exercise | Evidence required |
| --- | --- | --- |
| Two peers and AIs | Both humans select/move units, build, recruit and attack; allow AI construction and combat | Same ordered commands, actors, RNG and all eight resource blocks |
| Dense queues | Issue bursts from both humans, mixing categories and repeated orders | No untracked slots, missing commands or changed actor/order; reach many ring reuses |
| Automarket | Each human changes thresholds; exercise buy/sell, insufficient gold, stock thresholds, fees, market destruction/rebuilding | One execution per committed setting, matching resource checkpoints, no duplicate automatic trades |
| Pause and speed | Pause across a checkpoint and change speed through the supported game controls, including extended speeds when enabled | No duplicate checkpoints, no skipped simulation ticks; same final boundary |
| Long AI economy | Keep AI building, trading, recruiting and fighting through a longer window | Continued agreement and measured trace size/overhead; preserve any first mismatch |
| Host leave and resync | In a separate negative test, leave or trigger a real native resync inside the window | Valid linked replacement-world intervals, or an explicitly identified playable prefix; never a success claim across an uncovered gap |
| Departure after end | Leave after both bounded traces seal | Sealed files remain unchanged and comparable |
| Ascension/Steam | Repeat with the actual Ascension bundle and legitimate distinct Steam peers | Separate transport result; native TCP/IP loopback is insufficient |
| Extreme | Repeat with both peers on Extreme, including tactical powers | Variant-specific hooks and full interval evidence; no cross-variant comparison |

## Automated evidence already available

The observer tests cover 1,200 dispatched commands through six ring reuses with
an AI roster, pre-window receipt, paused end ticks, rearming on a new session,
early exit, missed boundaries, host events and footer write failure. Native
dispatch registers are preserved when logging fails. The comparator tests reject
identically truncated bounded traces and identify a resource difference in an AI
slot. These fixtures do not simulate DirectPlay delivery, Steam identity, packet
loss, latency or a full running AI simulation.

Development 0.18.0 live Crusader replay completed with Rat and Saladin. The
Automarket recording reached tick 69,573 with 13 commands, including a threshold
commit, an automatic sale, market construction/destruction and human defeat;
playback matched its RNG/resource checkpoints. See
[the live report](live-validation-0.18.md). That is single-player evidence and
does not establish multiplayer or full-world determinism.
