# Multiplayer diagnostics (0.19.0)

This stage observes execution and identity on each peer without changing the simulation scope, RNG seeds, pause flag, command ownership or dispatch decisions. Multiplayer recording/playback remains disabled. The existing single-player replay checks and isolation gates remain in effect.

## Collect and compare

From 0.32.0, diagnostic capture waits for the native simulation tick callback.
Loading and lobby RNG/network callbacks may contain the previous world's tick;
they cannot open or seal a capture. Payload receipts are retained for commands
that execute once the window opens. A session reset requires a new simulation
callback. Missing a requested boundary during actual gameplay still produces
an incomplete result, rather than moving the window to hide the omission.

1. Use the same test build on both peers, with the usual multiplayer extensions and Graphics API Replacer where required. Enable `multiplayerDiagnostics: true` in recorder's UCP configuration (the option defaults to false). Keep recorder after protocol in extension order.
2. For a comparable bounded test, configure the same `multiplayerDiagnosticsStartTick: 1024` and `multiplayerDiagnosticsEndTick: 8192` on both peers. These are absolute simulation ticks, not wall-clock seconds; both must be multiples of 64 and the end must be at least 64 ticks after the start. Play through the end tick with commands from both players and AIs in the match. Each trace seals automatically while gameplay continues. With the default end tick of zero, logging remains continuous until normal mission exit; a peer departure can mark that continuous trace incomplete.
3. Each game writes `ucp/replay-diagnostics/TIMESTAMP-NNNN/commands.jsonl`. Copy the two files into separately named peer-A and peer-B folders to preserve their identity.
4. Extract `tools/compare_multiplayer.py` from the module ZIP and run `python compare_multiplayer.py peer-A/commands.jsonl peer-B/commands.jsonl` with Python 3.10 or newer.

Exit codes: 0 means the compared command/RNG/resource evidence matched; 1 means it differed; 2 means the evidence was incomplete or incompatible. The JSON result identifies the first execution sequence/field difference, or the player/resource and amounts for an economy difference. Keep both original traces for analysis.

Bounded format 6 includes the requested window and requires every periodic
checkpoint from the start through the end. The final event must be the end
checkpoint, before that tick's native RNG advancement; the footer records that
boundary. Commands that reach dispatch before that final checkpoint are included;
events after sealing are outside the interval. Both peers must use the same
window. A missed start/end, early exit, incomplete handler or missing checkpoint
cannot become a successful comparison, even if both files omit the same data.
Commands received before the window remain available when they execute inside it.
After sealing, paused ticks, later commands and disconnection do not reopen the
file. A new match/session resets the capture. The interval before the requested
start and after its final checkpoint is explicitly outside this evidence.

## What is observed

The existing checked receive-copy and pre/post-dispatch sites observe timed commands from all senders. The actor comes from the native resolved-player field, rather than assigning every command to the local spectator. Every 64 simulation ticks, a read-only observer also records RNG/resource state immediately before native RNG advancement. It runs on the original simulation path without using the single-player halt flag. Repeated observations of a paused boundary are deduplicated. Each returned handler produces one row with the execution and scheduled ticks, category, payload, raw sender handle, native slot, resolved actor, post-command RNG and all eight players' resources. The comparator compares logical actors across peers, ignoring peer-local ring slots and transport-handle numbering differences. In format 4, each peer's handle-to-actor mapping must agree with its own captured roster.

A missing payload receipt produces an untracked row and an incomplete completion status. Interrupted handlers, write errors, missing footers and malformed records cannot become a successful comparison. Logging errors close the trace and disable further diagnostic writes for that session; they do not halt multiplayer or replace its command category. Trace files are flushed synchronously, so this opt-in instrumentation has I/O and execution overhead that still needs live measurement.

## Boundaries

This is command-boundary and periodic simulation evidence, not a full replay or a full world-state checksum. Immediate commands are detected but their full effects/payloads are not replayed; resynchronization/save transfers and private extension state remain unsupported. It does not make a multiplayer save playable offline, replace networking, or change human/AI identity rules. Equal traces therefore do not prove a complete multiplayer match is deterministic. Different post-command RNG/resource evidence locates a mismatch; further analysis is needed to establish its cause.

Automated tests use native callback fixtures to verify original registers/dispatch survive logging failures, remote actors are recorded, single-player does not start a multiplayer trace, and incomplete evidence is rejected. The comparator has matching/differing/corrupt trace tests. See [live findings](multiplayer-findings.md) for the first two-peer tests and their limits.

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

Lobby events before the trace opens are outside its window. Format 4 did not
individually log DirectPlay system messages: persistent roster/sync changes could
be noticed at later boundaries, but host-only or transient changes could escape
that sampling. Format 5 adds the observation below. Replaying host migration, a
synchronized starting snapshot, offline roster restoration, resync payload
reconstruction and native-versus-extension state coverage remain implementation
work. See the [native network-flow contribution](https://github.com/sourcehold/OpenSHC/pull/220).

The source investigation also confirms that the wire timestamp uses three bytes,
while command-ring ticks use four. A replay file must not silently equate these
formats. The reviewed RedirectPlay source forwards reliable flags but omits the
ReceiveData size output; the omission was also confirmed in the shipped Steam
1.2.3 DLL. A separate [RedirectPlay fix](https://github.com/gynt/RedirectPlay/pull/1)
has buffer/queue contract tests but still needs a live Steam test. Neither
replacing transport nor recording raw packets alone closes
the replay ownership and resync gaps.

## Format 5: DirectPlay system-message coverage

The native receive loop branches on `DPID_SYSMSG` (sender zero) after a successful
`IDirectPlay4A::Receive`. A new opt-in detour at Crusader `0x490735` / Extreme
`0x490895` observes that branch before its type switch. It retains the original
`MOV EAX,[EDI]; CMP EAX,3` instructions. Ordinary packets and failed/no-message
receives never enter it; the original-binary checker emulates those branches.

Native analysis of `receiveAllTransmittedCommands` (Crusader `0x490690`, Extreme
`0x4907F0`) establishes these paths. Type values also match `dplay.h` in the
OpenSHC DirectX SDK dependency:

| Type | Native effect relevant to recording |
| --- | --- |
| `0x0005` / `DPSYS_DESTROYPLAYERORGROUP` | Reads the transport handle at message offset 8, translates it to a player slot, then calls `removePlayerFromLobby` directly. |
| `0x0101` / `DPSYS_HOST` | Sets local host status, resets hash/timing counters, starts a wall-clock autosave timer and clears player timing arrays. It also updates chat and, outside a match, lobby ordering. |
| `0x0003` / `DPSYS_CREATEPLAYERORGROUP`, `0x0031` / `DPSYS_SESSIONLOST` | This native switch skips them. The diagnostic stage still records their occurrence conservatively. |
| Other values | Native fallback formats a message; the recorder does not infer replay safety from that. |

Every observed system message in an open trace produces a `gap` row and an
incomplete footer, even if the next sampled roster and sync phase are unchanged.
The details include type and declared receive size; a destroy-message handle is
included only when the declared size covers its first 12 bytes. No pointers in
the system structure are followed, and no raw pointer-bearing payload is saved.
The receive size is provider-supplied diagnostic metadata, not proof that all
those bytes were delivered; the RedirectPlay size-output concern above still
applies. Invalid declared sizes disable diagnostics without altering native
execution. A logging failure has the same isolation behavior.

The comparator rejects these gaps and mixed format-4/5 pairs. Matching format-5
traces still certify only the observed window and compared state, not a complete
replay. Events before the first recorded boundary, resync contents and extension
state remain outside that claim. This stage detects an unsupported transition;
it does not reproduce or suppress it. No live two-peer test was performed.
