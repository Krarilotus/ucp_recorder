# SHC / Extreme address verification

The port uses separate, checked profiles for the original 1.41 executables. All
patch bytes are checked before the first patch is installed. The SHA-256 in each
profile documents the binary used for analysis; runtime selection checks the
patch sites, rather than assuming every file called `Stronghold Crusader.exe`
has the expected layout.

| Item | Crusader | Extreme |
| --- | --- | --- |
| GameSynchronyState | `0191d768` | `023547d8` |
| Current local handle offset | `6a4` | `6a4` |
| Current player slot offset | `109e74` | `166304` |
| Command ring write index offset | `109ee0` | `166370` |
| Command ring offset / stride | `3c67c` / `1272` | `3c67c` / `1272` |
| RNG structure | `01a279c0` | `024baec0` |
| Simulation tick | `01fe7da8` | `02a7b2a8` |
| Native received-command scheduler | `00480210` | `004803e0` |
| Player identity translation | `0047eaf0` | `0047ecc0` |
| Skirmish menu items | `005e9848` | `005e9708` |

Instruction signatures were matched between executables with relocation operands
masked, then the differing operands were inspected. In particular, Extreme grows
the synchrony structure: applying a single address delta to both its beginning
and its current-player fields would be incorrect. The menu constructor's object
reference and the next array boundary also confirm the relocated menu array.

Ghidra's named SHC program and OpenSHC's reconstructed classes were used to check
field meanings and calling conventions. The dust-spawn replacement occupies the
entire five-byte CALL and performs its 44-byte argument cleanup in both builds.

This port does not make recordings portable between game variants. Session files
must retain the variant and compatible simulation settings. Multiplayer is a
separate capability and is not implied by locating Extreme's command scheduler.

For an optional check against your legally installed originals:

```
python tests/check_executables.py "path/to/Stronghold Crusader Extreme"
```

The check reads both files and exercises profile selection through LuaJIT; it
does not launch, patch or redistribute the executables.
