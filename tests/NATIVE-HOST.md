# Console checks with the installed runtime

Compile `lua_rps_host.cpp` in an x86 Visual C++ command environment:

```bat
cl /nologo /W4 /WX /MT /O2 /Felua_rps_host.exe lua_rps_host.cpp /link /MANIFEST:NO kernel32.lib
```

Put the host beside copies of the installation's `lua.dll` and `RPS.dll` in a
private test directory. It calls `RPS_setLuaState`, which is needed for callbacks;
loading the Lua RPS library alone only exposes its functions. Run from that directory:

```bat
lua_rps_host.exe <recorder>/tests/check_input_chain_windows.lua <recorder> <framework>/content/ucp/code <winProcHandler-1.0.0.dll>
lua_rps_host.exe <recorder>/tests/check_binary_memory_windows.lua <recorder> <framework>/content/ucp/code <cffi.dll>
lua_rps_host.exe <recorder>/tests/check_pause_menu_windows.lua <recorder> <framework>/content/ucp/code <cffi.dll> <ui>/ui/headers/latest/ui.h <ui>/ui/menu.lua
```

Use DLLs from the correctly versioned module ZIPs. The input check requires
WinProc Handler 1.0.0's exports; 0.2.0 is insufficient. These checks use private
allocations, native callbacks and Windows services without launching or attaching
to a game. They do not establish live input, simulation or replay acceptance.
The pause check uses the actual UI 1.0.1 source extracted into that private test
directory, exercising its insertion API rather than a replacement array owner.

# UI binding discovery against private images

`check_ui_bindings.py` runs without a game or desktop access. Supply a licensed
Crusader 1.41 or Extreme 1.41 executable, the installed UI 1.0.1 `ui/game.lua`,
and framework 3.0.7's code directory. It uses the actual UI Lua source and
framework extractor, with numeric pointers at the CFFI boundary:

```text
python tests/check_ui_bindings.py --reference "path/to/Stronghold Crusader.exe" --variant SHC --ui-game "path/to/ui/game.lua" --framework-code "path/to/ucp/code" --output "path/to/evidence.json"
```

Repeat with the Extreme executable and `--variant Extreme`. Requirements:
`pefile` and `lupa` (Lua 5.4). This verifies discovery/context and rejects conflicts;
it does not establish installed-game, render, multiplayer or replay acceptance.
