# Delayed AI replies and native command layouts (0.23.0)

An AI's reply to a taunt can advance simulation RNG according to elapsed real
time. The replay stores simulation commands, so different rendering speeds or
pauses need not reproduce that advance at the same simulation boundary.

## Delayed reply

The complete native routine at Crusader `0x4D10B0` / Extreme `0x4D1300`:

1. Checks the in-game predicate and Skirmish single-player mode `99`.
2. Requires a pending reply timer and unsigned `timeGetTime() - timer > 2000`.
3. Builds a weighted list of enemy AI players and reads the current RNG1 value.
4. Advances RNG1 at `0x4D11F1` / `0x4D1441`, then uses the **previous** value to
   select a speaker and taunt. It sets recipients, queues command14 and clears
   the timer.

The recorder now skips only that RNG advance while its single-player simulation
scope is active. The surrounding selection, clock checks, message parameters
and timer cleanup remain. Playback's existing queue guard blocks newly generated
local commands. The patch does not globally disable RNG or change normal idle
and multiplayer execution. This routine's own mode check already excludes MP;
this finding does not explain the earlier multiplayer RNG difference.

Simulation profile `recorder-sp-v9` separates these recordings from older RNG
histories. Old files remain on disk and can be used with their original release;
they are not migrated by changing their profile string.

## Timed payloads versus immediate chat

Crusader command14's handler at `0x4895E0` / Extreme `0x4896F0` writes a payload
size of `0x220` (544), forces the command timestamp to zero, and uses the separate
fixed message buffer. Its fields are a four-byte chat/taunt value, 500 bytes of
wide text, 36 recipient bytes and a four-byte speaker parameter. It must not run
through the timed ring's payload path. Category14 is therefore removed from
the timed replay allowlist. Chat/taunt display and sound are not recorded by this
release; the simulation RNG guard addresses their separate determinism effect.

Every other supported native timed category now has an exact payload length:

```text
15:4   17:8   18:5   19:5   20:6   21:10  22:6   23:6   24:6
25:12  26:6   27:6   28:10  29:7   31:3   34:1   35:1   36:15
38:2   41:5   42:7   43:2   44:5   45:7   68:10  69:9   70:3
71:7   78:2   113:18
16:402 (Crusader), 1252 (Extreme); 119:8 (Extreme only)
```

The native handlers declare these lengths in receive phase2 while preserving the
timed header's timestamp. Session preflight and dispatch reject shorter or longer
payloads, including files with internally consistent checksums. Automarket122
keeps its separately verified 272-byte adapter. Extensions that change native
packet layouts require an explicit adapter; a matching extension version does
not make an unknown wire layout supported. Length checks do not establish every
payload field's semantic validity.

## Evidence and remaining live checks

`check_command_layouts_native.py` executes all supported native handlers in
phase2, plus chat14, at ring slots0/199 with three timestamps. All390 cases across
both original executables verify size, timestamp behavior, stack and callee-saved
registers, without substituting the handlers.

`check_taunt_native.py` executes the complete original reply routine and original
RNG method with the actual emitted gate. All220 cases cover eight RNG values,
the2000/2001ms boundary, inactive and MP modes, no pending timer, no eligible AI,
the in-game predicate and clock wrap. Menu/clock return values and queue delivery
are controlled test boundaries. Speaker/message bytes and timer behavior match
the original; active SP retains the full RNG state. The emulator cache is cleared
between rewritten gate/clock scenarios so every case runs its current code.

Portable tests cover malformed lengths, variant-specific selection/powers,
checksum-valid corrupt streams and old-profile rejection. Original-executable
checks also retain the earlier native dispatch, capture, immediate-buffer and
RNG-observer regressions.

These are code/emulation results, not a new live gameplay pass. Next, taunt enemy
AIs while recording, vary speed and pause duration, then replay through the same
ending boundary in both variants. Full world-state, extension private-state and
multiplayer reconstruction gaps remain.
