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
```

Use DLLs from the correctly versioned module ZIPs. The input check requires
WinProc Handler 1.0.0's exports; 0.2.0 is insufficient. These checks use private
allocations, native callbacks and Windows services without launching or attaching
to a game. They do not establish live input, simulation or replay acceptance.
