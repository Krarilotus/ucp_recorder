# Recorder 0.52.0 compatibility

0.52.0 lets replay restore points contain every module's saved data when Map
Extensions provides its save archive API. Without that API, Recorder keeps the
0.51.1 behaviour. The required dependencies are unchanged:
**framework >=3.0.7; UI ^1.0.1**. Map Extensions, Automarket, UCP2-Legacy and
other stateful modules stay optional.

## Where restore-point state comes from

| Setup | Extension section in a restore point | Seeking |
| --- | --- | --- |
| No Map Extensions | None. There is no extension save data to keep. | Restore points |
| Map Extensions 1.0.0 (Store) | Recorder's own adapter: Automarket 1.1.0's saved data and UCP2-Legacy 2.15.2's simulation state, as in 0.51.1 | Restore points |
| Map Extensions with `captureSaveSection()` (1.2 candidate) | The owner's complete archive: every registered section, written by the same ZIP writer as a normal save | Restore points, marked `sectionCapture=1` |
| Another Map Extensions 1.x without that API (not in the Store) | Not written. The adapter cannot see required sections such as Improved Tunnelers'. | From the starting save |
| Map Extensions 2.x | Recorder does not start, as before | — |

Automarket 1.1.0 and UCP2-Legacy 2.15.2 already register their sections with
Map Extensions. With the archive API, Recorder uses those registrations and
reads neither Automarket's data pointer nor Legacy's export. The adapter is
only the fallback for Map Extensions 1.0.0.

With the archive API, Recorder also checks the save functions that Map
Extensions resolved (`getNativeSaveInterface()`). When they are exactly the
functions of Recorder's verified game profile, Map Extensions' own wrapper
replaces Recorder's byte check at those two functions. If the interface is
missing, fails, has another version or names other functions, Recorder keeps
its checked static addresses, as with 1.0.0.

## Limits

- An extension section of up to 32 MiB is accepted at capture. A restore point
  must still fit Recorder's native container (6,000,000 stored bytes for the
  world plus the section) and the 7 MiB restore point limit. A larger world
  fails safely when it is written: that restore point is skipped and seeking
  replays from the starting save.
- With Map Extensions 1.0.0, Recorder's adapter loads Map Extensions' ZIP
  library from `ucp/modules/map-extensions-<version>/`, the folder of an
  installed Store package. Map Extensions has no API for its ZIP library; the
  archive API replaces this path with 1.2.

## UCP2-Legacy

When UCP2-Legacy is active, Recorder needs **2.15.2** or newer, as since 0.45.0.
Version 2.15.1 keeps the AI attack target cycle, wall-defense counts and ladder
destinations outside saved worlds, so a replay can desync even with matching
RNG. 2.15.2 is in the 3.0.7 Store, and Vanilla Retraced and UCP2-Legacy Defaults
accept it (`^2.15.1`). With 2.15.1, Recorder shows its startup message, stays
off for that launch and the game continues. Without UCP2-Legacy, there is no
Legacy requirement.

## Older replays and restore points

Replay and restore point formats are unchanged. `sectionCapture` is an
additional field. An older point still loads unless Map Extensions reports an
active required provider (such as Improved Tunnelers), whose data that point
could not contain; then seeking starts from the replay's starting save and
plays forward, which takes longer.

A replay keeps the exact versions it was recorded with. A replay recorded with
0.51.1 is played by Recorder 0.51.1 after the usual settings restart, so keep
that version installed for older recordings.

## Multiplayer

Multiplayer recordings, their world evidence and offline playback follow the
same table. Loading a multiplayer save made with a different set of modules,
versions or settings is not advised.
