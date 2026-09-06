# Automatic recording and the replay library (0.17.0)

New single-player Skirmishes are recorded by default. The UCP option **Record Skirmishes automatically** sets the launch default; **Auto: on/off** in the lobby toggles it for subsequent matches during this game launch. Disabling it does not delete earlier recordings. Native loaded saves, campaigns, multiplayer and replay playback do not automatically start a new recording.

The game validates the lobby before the recorder arms, at Crusader `0x442877` / Extreme `0x442A37`, immediately before the native seed setup. This preserves the timing of manually arming in earlier builds. The existing post-launch callback requests the snapshot at the first simulation boundary. Leaving the mission through the normal game menu completes and saves the full recording automatically. Forced termination and unsupported native commands still leave an incomplete/failed capture, not a playable replay.

## Save replay as...

The native pause/options menu gains **Save replay as...** beneath its original actions while recording. Enter a name and press Enter or **Save name**. A confirmation shows the saved name, and the original capture continues. Escape or Cancel returns without saving. The name editor supports selection replacement, arrows, Home/End, Delete and Backspace, with 1-40 printable ASCII characters. The UI does not borrow the game's save-name, chat or player-name buffers.

This saves a separate replay from the original starting snapshot through the last observed simulation boundary. It flushes and copies replay files, validates the copied snapshot/settings and seals the copy. It does not issue a native save command or reset the active session. Failed copies remain unplayable and leave the original streams intact. Identically named copies have different directory IDs. The library's **Rename replay...** changes only the completed replay's display name.

## Native graphics and input

The controls use the original `interface_icons3` tiled button skin via `renderBasicButton`, the initialized HD font slot 19, gold outlines and the game's red modal frame. Outlines remain visible without hovering; hover and selection add an inner outline. The browser and name editor use native MenuItem hit testing. The lobby entries remain in the gaps between the original bottom-row controls.

The pause menu retains its nine original entries and sentinel; one independent item is appended at `(100,342,300,27)`. Its height expands from 357 to 405 only when a recorder session/error is present in single-player, before the native modal copies and rounds the dimensions. New submenus retain the existing pause stack. One shared menu hook controls visibility for both arrays, avoiding duplicate detours of the same prologue.

| Native boundary | Crusader | Extreme |
| --- | --- | --- |
| Pause item-array constructor operand | `0x59AD80` -> `0x6001D8` | `0x59B1B0` -> `0x6000E8` |
| Pause modal | `0xDF51C8` | `0xDF5260` |
| Original tiled button renderer | `0x463A90` | `0x463CA0` |
| Window message handler | `0x4B2AE0` | `0x4B2C50` |

Keyboard messages are consumed only while one of this module's dialogs is actually active and the game is single-player. Mouse, system/Alt messages and all messages outside those dialogs follow the original handler. WindowProc uses four stdcall stack arguments; UCP's five-argument thiscall bridge supplies an unused ECX and the same 16-byte callee cleanup. The native function overwrites incoming ECX before reading it. The eight-byte prologue consists of two complete, position-independent instructions. This bridge still needs live UCP validation; tests of Lua callbacks are not a substitute for it.

## Playing with recorded settings

**Play** checks the saved executable, simulation profile, configuration bytes, resolved configuration, extension versions and Automarket descriptor. Matching sessions load their own starting save and RNG state. Different configuration bytes queue the existing hidden helper; exit normally to let it relaunch with that replay's `ucp-config.yml`. Open Skirmish > Replays and press Play on the preselected recording. The normal configuration file remains unchanged.

If configuration bytes already match but the resolved environment differs, another identical restart cannot repair that mismatch. The UI asks for the recorded extension/framework versions instead. The helper does not install missing versions. Version equality also cannot detect local edits to unpacked modules or changed external assets.

## Validation boundary

142 portable tests cover recording defaults/exclusions, repeated capture, file copying and failure, rename isolation, actual menu actions and settings routing, keyboard editing, modal bounds and native-hook isolation. Read-only checks verify the original menu layout and hook bytes on both executables, alongside the earlier native dispatch/RNG harnesses. The new graphics, keyboard bridge, complete gameplay replay and restart handoff have not been confirmed in a live game. Multiplayer playback remains disabled.

For the next live pass, test default capture, pause-menu naming/cancel/save, continued capture after a named copy, normal-exit saving and playback of both copies. Repeat at 800x600 and a normal HD resolution on both variants, then change UCP settings and verify the restart, selected replay and unchanged normal configuration.
