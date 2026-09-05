# Multiplayer diagnostics (0.11.0)

This is the first multiplayer-specific implementation stage. It observes execution on each peer without changing the simulation scope, RNG seeds, pause flag, command ownership or dispatch decisions. Multiplayer recording/playback remains disabled. The existing single-player replay checks and isolation gates remain in effect.

## Collect and compare

1. Use the same test build on both peers, with the usual multiplayer extensions and Graphics API Replacer where required. Enable `multiplayerDiagnostics: true` in recorder's UCP configuration (the option defaults to false). Keep recorder after protocol in extension order.
2. Play a short match with commands from both players. Exit the match normally so the trace can write its completion record.
3. Each game writes `ucp/replay-diagnostics/TIMESTAMP-NNNN/commands.jsonl`. Copy the two files into separately named peer-A and peer-B folders to preserve their identity.
4. Extract `tools/compare_multiplayer.py` from the module ZIP and run `python compare_multiplayer.py peer-A/commands.jsonl peer-B/commands.jsonl` with Python 3.10 or newer.

Exit codes: 0 means the compared command/RNG/resource evidence matched; 1 means it differed; 2 means the evidence was incomplete or incompatible. The JSON result identifies the first execution sequence/field difference, or the player/resource and amounts for an economy difference. Keep both original traces for analysis.

## What is observed

The existing checked receive-copy and pre/post-dispatch sites observe timed commands from all senders. The actor comes from the native resolved-player field, rather than assigning every command to the local spectator. Every 64 simulation ticks, a read-only observer also records RNG/resource state immediately before native RNG advancement. It runs on the original simulation path without using the single-player halt flag. Repeated observations of a paused boundary are deduplicated. Each returned handler produces one row with the execution and scheduled ticks, category, payload, raw sender handle, native slot, resolved actor, post-command RNG and all eight players' resources. The comparator ignores peer-local player identity, raw handles and ring slots, comparing the resolved actions and resulting evidence instead.

A missing payload receipt produces an untracked row and an incomplete completion status. Interrupted handlers, write errors, missing footers and malformed records cannot become a successful comparison. Logging errors close the trace and disable further diagnostic writes for that session; they do not halt multiplayer or replace its command category. Trace files are flushed synchronously, so this opt-in instrumentation has I/O and execution overhead that still needs live measurement.

## Boundaries

This is command-boundary and periodic simulation evidence, not a full replay or a full world-state checksum. It does not yet capture untimed commands, resynchronization/save-transfer packets or private extension state. It does not make a multiplayer save playable offline, replace networking, or change human/AI identity rules. Equal traces therefore do not prove a complete multiplayer match is deterministic. Different post-command RNG/resource evidence locates a mismatch; further analysis is needed to establish its cause.

Automated tests use native callback fixtures to verify original registers/dispatch survive logging failures, remote actors are recorded, single-player does not start a multiplayer trace, and incomplete evidence is rejected. The comparator has matching/differing/corrupt trace tests. No live multiplayer match was launched for this stage.

Format 2 gives every command/checkpoint an ordered evidence sequence and records both event and command totals. The comparator detects skipped checkpoint boundaries, including matching files with the same missing interval. It accepts older format-1 pairs as command-only evidence; mixing formats is rejected. A short interval before the first recorded event is outside the trace window.

Format 3 additionally records SHA-256 of the complete 40,016-byte RNG structure at
each periodic checkpoint, detecting differences in stored random arrays before
they appear in the current values/indices. Command rows retain their smaller
post-handler RNG summary. The header includes the resolved UCP settings,
framework and extension order/version environment hash; different environments
are reported as incompatible. This does not fingerprint edited extension files
or external assets. Older format-1/2 pairs can still be compared with their
original evidence limits. Full RNG hashing adds periodic CPU work; live overhead
and two-peer comparisons still need measurement.
