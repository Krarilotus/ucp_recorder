# Multiplayer diagnostics (0.13.0)

This stage observes execution and identity on each peer without changing the simulation scope, RNG seeds, pause flag, command ownership or dispatch decisions. Multiplayer recording/playback remains disabled. The existing single-player replay checks and isolation gates remain in effect.

## Collect and compare

1. Use the same test build on both peers, with the usual multiplayer extensions and Graphics API Replacer where required. Enable `multiplayerDiagnostics: true` in recorder's UCP configuration (the option defaults to false). Keep recorder after protocol in extension order.
2. Play a short match with commands from both players. Exit the match normally so the trace can write its completion record.
3. Each game writes `ucp/replay-diagnostics/TIMESTAMP-NNNN/commands.jsonl`. Copy the two files into separately named peer-A and peer-B folders to preserve their identity.
4. Extract `tools/compare_multiplayer.py` from the module ZIP and run `python compare_multiplayer.py peer-A/commands.jsonl peer-B/commands.jsonl` with Python 3.10 or newer.

Exit codes: 0 means the compared command/RNG/resource evidence matched; 1 means it differed; 2 means the evidence was incomplete or incompatible. The JSON result identifies the first execution sequence/field difference, or the player/resource and amounts for an economy difference. Keep both original traces for analysis.

## What is observed

The existing checked receive-copy and pre/post-dispatch sites observe timed commands from all senders. The actor comes from the native resolved-player field, rather than assigning every command to the local spectator. Every 64 simulation ticks, a read-only observer also records RNG/resource state immediately before native RNG advancement. It runs on the original simulation path without using the single-player halt flag. Repeated observations of a paused boundary are deduplicated. Each returned handler produces one row with the execution and scheduled ticks, category, payload, raw sender handle, native slot, resolved actor, post-command RNG and all eight players' resources. The comparator compares logical actors across peers, ignoring peer-local ring slots and transport-handle numbering differences. In format 4, each peer's handle-to-actor mapping must agree with its own captured roster.

A missing payload receipt produces an untracked row and an incomplete completion status. Interrupted handlers, write errors, missing footers and malformed records cannot become a successful comparison. Logging errors close the trace and disable further diagnostic writes for that session; they do not halt multiplayer or replace its command category. Trace files are flushed synchronously, so this opt-in instrumentation has I/O and execution overhead that still needs live measurement.

## Boundaries

This is command-boundary and periodic simulation evidence, not a full replay or a full world-state checksum. Immediate commands are detected but their full effects/payloads are not replayed; resynchronization/save transfers and private extension state remain unsupported. It does not make a multiplayer save playable offline, replace networking, or change human/AI identity rules. Equal traces therefore do not prove a complete multiplayer match is deterministic. Different post-command RNG/resource evidence locates a mismatch; further analysis is needed to establish its cause.

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

## Format 4: ownership and uncovered network events

Locally queued timed payloads are captured before transmission at `0x489216`
(Extreme `0x489326`). They enter the command ring directly and never traverse
the receive-copy hook. Each command row identifies its local/received origin;
the comparator ignores that peer-relative origin and compares actual execution.

The header records mode, local slot, synchronization status, eight transport
handles and a logical roster (human/AI/empty, AI ID and variation). Native
classification treats handle -1 plus a nonzero AI ID as AI. Duplicate human
handles, system-message handle zero, missing roster data and an active resync
phase are rejected by the comparator. Human handle numbering may differ between
the two files, but each command must map to its actor in that file's own roster.

While a trace is open, identity and synchronization state are checked at every
simulation boundary and before timed dispatch. Changes produce `gap` rows and
an incomplete footer. Separate read-only detours cover immediate dispatch from
both received commands (`0x480417`, Extreme `0x4805E7`) and locally queued
commands (`0x4892BE`, Extreme `0x4893CE`). These hooks retain the original MOVSX
instructions and do not suppress execution. Any such dispatch in the trace
window produces a gap with its category, actor, declared size and source.
Harmless immediate commands can therefore also make this conservative stage
incomplete; there is no unaudited whitelist.

Lobby events before the trace opens are outside its window. DirectPlay system
messages are not yet individually logged: persistent roster/sync changes can be
noticed at later boundaries, but a transient change between observations can
escape that sampling. Host migration, a synchronized starting snapshot, offline
roster restoration, resync payload reconstruction and native-versus-extension
state coverage remain implementation work. See the [native network-flow
contribution](https://github.com/sourcehold/OpenSHC/pull/220) for the evidence.

The source investigation also confirms that the wire timestamp uses three bytes,
while command-ring ticks use four. A replay file must not silently equate these
formats. The reviewed RedirectPlay source forwards reliable flags but omits the
ReceiveData size output; its exact correspondence to the shipped DLL remains
unverified. Neither replacing transport nor recording raw packets alone closes
the replay ownership and resync gaps.
