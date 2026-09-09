# Recording and saved snapshots

See [menu controls](replay-menus.md) for the current native history and playback UI.

Recording is enabled by default for supported single-player Skirmishes, loaded
Skirmish saves and multiplayer sessions. A named save copies the starting world
and recorded prefix through the last observed boundary. It does not stop or
rename the continuing full recording. Native statistics are frozen at that same
boundary, using the game's existing accumulated counters.

Full recordings are sealed when leaving normally. Settings, initial state and
streams are verified before playback. Files from an abrupt crash are preserved;
they must not be described as a verified playable recording.

Replay names are currently limited to 1-40 printable ASCII characters. The name
editor owns its buffer and does not borrow native save-name, chat or player-name
storage. Older diagnostic recordings without native statistics are not migrated.
