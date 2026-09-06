# Rally points and stopped recordings

The live 0.26.0 capture `20260906-203420-0001` stopped after 65 recorded commands,
at tick 30,157, because the next command was category 102. The console reported
an unsupported replay command, not RNG divergence. That running process had
not been restarted into the published church fix. The same command omission
was also present in 0.27.0.

Native command 102 is `SetUnitAssemblyPoint`, not a network or save/load command.
Its five-byte payload is one signed-byte assembly-point selector and two
16-bit coordinates. The handler applies the acting player's rally point and
can clear it when clicking the appropriate owned recruiting building. This
includes the cathedral, alongside barracks, mercenaries and guilds.

| Native function | Crusader | Extreme |
| --- | --- | --- |
| Command 102 handler | `485830` | `485A60` |

The original receive-phase tests check the exact five-byte size, native ring
slots, timestamp retention and ABI on both executables. File validation rejects
truncated and extended payloads. Native gameplay interprets the captured bytes
through its original handler; no separate rally-point implementation is added.

The subsequent disabled trade/troop/ally controls had another recorder cause:
the failed recording stayed active, so the dispatch hook replaced later commands
with a no-op. Local UI previews could still appear. From 0.28.0, a recording
failure pauses once, marks the capture failed, closes its streams, clears its
pending capture state and disables the replay simulation scope. Native live
commands continue through their original handler. Unpausing resumes ordinary
gameplay, but that failed capture never becomes a completed replay.

Playback failure remains fail-closed because continuing a divergent recorded
world or executing malformed file-controlled commands would be misleading.
The pause-menu failure entry explains which state occurred. Preventing all
local construction previews during playback still needs the separate spectator
input work tracked in the roadmap.

Tests cover the actual session guard plus installed dispatch callbacks: an
unsupported live command fails recording, then trade/troop/building/rally/ally
commands remain intact after ordinary unpause. Playback rejection tests remain.
Additional tests cover close errors, preservation of the first failure, no
resumed capture, no false completion and distinct menu messages.

Next live test: restart with 0.28.0, start a fresh recording and set a cathedral
or barracks rally point. Exercise troop orders, trade and allied requests;
inspect a staffed church's wedding panel and finish normally. Check the replay
through its ending tick, then repeat with different speed/pause/inspection.
