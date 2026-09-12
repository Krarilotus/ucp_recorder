# Runtime binding correction

The existing fixed SHC/Extreme address profiles remain unfinished work. This
branch corrects dependencies one complete path at a time; it does not yet claim
an AoB-complete Recorder or installed-game/replay acceptance.

## Windows services

Inspected framework 02a7a6b, `dll/core/initialization/ucp-internal.cpp`, and its
pinned RPS 1.5.2 implementation at 09fcf31, `RuntimePatchingSystem.cpp` and
`LibraryFunctions.cpp`. UCP exposes `getLibraryProcAddressA` in `ucp.internal`;
it loads the library and delegates export/forwarder resolution to Windows.
Recorder's own standalone binary-memory check already calls this API.

Use that owner for Kernel32, Advapi32 and WinMM functions. Remove the private
PE export parser and game-IAT profiles from `code/platform.lua`. Retain the
existing stdcall bridge because the target RPS `exposeCode` implements cdecl
and thiscall, not stdcall. The framework continues to allocate and expose it.
Resolve each requested function once, retaining the callable and its ABI count;
there is no game-version dependency or scan in these Windows-service calls.

CFFI 1.0.0 was also inspected at module 80c70e2 / cffi-lua 5a675d8, including
`lib.cc`, the installed module export and its loader/calling-convention tests.
It provides a system loader, but the framework already exposes the required
address resolver, so no additional dependency or C declaration registry is needed.

This correction concerns symbol resolution, not replay executable/content
fingerprints. Recording identity remains a separate contract.

Validation: 478 portable tests pass (one existing skip); the stdcall test executes
nine argument-count variants in x86 emulation. The production Windows-service
path also passes in a private console host with the installation's 32-bit Lua,
RPS and CFFI DLLs: unsigned clocks, process identity, no repeated resolution,
binary copy boundaries and native SHA-256 self-tests. The old standalone resolver
override was removed, so this check executes `platform.stdcall` itself. No game
was launched for these tests.

## Window input

WinProc Handler 1.0.0 at 5f85672 exports `cinterface()`, supplying RegisterProc,
CallNextProc and GetMainProc. Its `dllmain.cpp` owns the ordered callback map,
collision-adjusted registration priority and final native WindowProc dispatch.
Inspected its callers in Custom Hotkeys `code/native/chain.lua` as well; Recorder
uses the published Lua interface rather than opening the same DLL again.

`code/input-chain.lua` replaces Recorder's direct game WindowProc hook. The
private RPS callback has five stdcall stack arguments, using the existing
thiscall bridge with an unused ECX argument. It forwards the incoming priority
and all message arguments unchanged. Recorder registers at 100000, retaining
its previous position after ordinary remapping/graphics processing; priority
collisions use the owner's actual result. Replay speed buttons continue from
that assigned priority without re-entering Recorder's overlay or posting input.
Callbacks and their bridge stay alive for the process: the owner has no unregister.

WinProc Handler 1.0.0 is now an explicit dependency. The old test installation
contained 0.2.0, which lacks the Lua interface; it cannot satisfy this dependency.
Legacy, WinProc Handler and Hotkeys source are unchanged.

Native console acceptance uses the actual 1.0.0 DLL (SHA-256
`af831149cc71ff621be7eee55ad74ce74703598d2e37798eca1c817921222414`), installed
Lua/RPS, and private allocations only. It passes priority collisions, normal
forwarding/return values, consumed input, tail dispatch, contained callback
errors and 1000 repetitions. The host must call RPS_setLuaState as UCP does;
luaopen_RPS alone does not initialize native callback state. This test does not
establish live-game keyboard/graphics/Hotkeys composition acceptance.
The full portable suite passes 481 tests with one existing skip. The init fixture
now includes the declared input owner and the framework code-size operation.

## Pause menu insertion

The installed UI 1.0.1 `ui/menu.lua` exports `Menu:fromPointer` and
`Menu:insertMenuItem`; `manager.lookupModalMenu(5)` supplies the initialized
pause modal. Automarket 858890f uses this insertion API during framework
`afterInit`, after native construction and before the Windows message loop.
The actual CFFI implementation was exercised before adopting it here.

Recorder now inserts its pause item through that owner at the same lifecycle
boundary and retains the returned menu/allocation. It removes the private copy
of the whole pause array and the constructor-operand patch, along with both
fixed pause bindings. Restart control snapshots are taken after native callback
initialization, located again in the current array when toggled, and restored
without overwriting appended controls. Height changes retain other additions.

The console check with actual UI source and installed CFFI/Lua/RPS passes
insertion, preserved native callbacks/rows/sentinel, restart disabling/restoring,
later owner reallocation, additive height changes and retained allocations after
collection. Portable tests cover afterInit timing and the production consumer.
Live pause-menu/replay acceptance remains outstanding. This does not yet remove
the remaining UI callable/hook profiles; existing UI exports are the next reuse path.

## UI binding inventory

Inspected installed UI 1.0.1 and source d3a807c (`ui/game.lua`, `manager/init.lua`,
`init.lua`), its CFFI ABI declarations and the Automarket caller. Before Recorder
installs any UI hooks, `ui:access()` resolves its main-state exports. Reuse
`UI.Menu`, `UI.MenuModal`, `UI.activateModalMenu`, `Rendering.renderTextToScreenConst`,
`Rendering.drawBorderBox` and `Rendering.renderButtonBackground`. Reuse its text
manager, pencil, color, button state/surface, mouse and modal-composition pointers,
and `manager.getState().modalMenuStackTop`. Verify callable instruction context
at the owner's returned pointer; do not scan again for these exports.

The inspected API has no exports for menu update/dispatch, player-summary and
building-status render boundaries, report admission, header/portrait rendering,
text width, clipped/masked mission sprites or map viewport coordinates. Recorder
already owns these replay presentation hooks; replace their private address
profiles with framework AoB discovery and decoded operands. Derive the hit flag
from the verified menu-update body rather than scanning for it separately.
Resolve once at preflight, reject absent/ambiguous/modified contexts, then retain
the original overwritten bytes for UCP's existing hook facilities. No new hooks
or simulation work are added. Recorder's broader lifecycle/world profiles are
still separate unfinished work; this inventory does not authorize a fixed-address
fallback or removing their current guard while those profiles remain.

The UI profile table is now removed from production. Six callable addresses and
eight data pointers come from UI; thirteen further contexts use framework scans.
Native operands supply the remaining roots. Each hook checks the full captured
preflight context immediately before installation, including operands and code
beyond the overwritten prologue. This adds no scans or work to simulation ticks.

Both private SHC 1.41 and Extreme 1.41 images pass all 29 named bindings and 34
negative cases each with the installed UI `ui/game.lua` and actual framework
`utils.AOBExtract`. The CFFI boundary in this image check returns numeric pointers;
it does not execute game code. Existing original-instruction presentation checks
cover the native calling conventions separately. Portable Lua 5.4/LuaJIT tests
cover relocated bindings, absent/ambiguous sites, missing owner exports, conflicting
operands and a change after preflight. See `tests/check_ui_bindings.py`.
The full portable suite passes 484 tests (one existing skip). Original-instruction
header, mission-bar raster/clip, menu-input and 192 report-admission cases per
game family pass. Rendering stand-ins are identified by each native harness;
the mission TGX check executes the original rasterizer against private surfaces.

This is not a completed Recorder binding port: lifecycle, engine, world, history,
network and other existing fixed profiles still remain. Installed UI/Hotkeys/game
composition, language/distribution variants and live replay acceptance are pending.
