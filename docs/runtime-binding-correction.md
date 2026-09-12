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

## Save owner bindings

Map Extensions 1.1.1 at 9d35dfb exposes `getNativeSaveInterface()` from the
existing `mapextensions/game.lua` owner. Its original section table, packager
and read/write entries already come from framework scans. Recorder now requires
that API and uses those wrapped entries, preserving Map's before/after callbacks
and required/custom-section substitution. Four fixed fields per engine profile
and both duplicated section-table addresses are removed. No save hook is added,
no original trampoline is bypassed and no replacement section registry is built.

The public interface is checked before Recorder installs anything. Native-world
capture reads the owner's section table as well. Existing fixed descriptor-table
fingerprints are still retained by `world-layout.lua`; replacing that restriction
with validated native schema/identity is unfinished, along with the other engine
and lifecycle bindings. This change alone does not broaden Recorder's executable
acceptance or establish live save/replay compatibility.

The inspected Protocol changes through 1.1.2 do not modify its command interface,
hooks, helpers or Automarket wire layout. Map 1.1.1 changes metadata exposure only;
its callbacks, required providers and native ZIP DLL remain unchanged. Recorder's
Automarket adapter now recognizes those revisions. The existing ZIP consumer uses
the framework's active Map alias; `core.openLibraryHandle` resolves aliases before
opening the library (`core.lua` at 02a7a6b). This removes a stale version-built
library path without adding a loader or touching live serialization.

Validation: 486 portable tests pass (one existing skip), including the actual
Map owner and Recorder consumer at relocated fixture addresses, both wrappers,
callback order, section substitution, missing/incompatible metadata and zero new
scans. An installed 32-bit Lua console check with the shipped native ZIP DLL
(`a4dfd1beb49b09f8e2c52ad680101bd8843c9c008988268610442b7b85e1cc7c`)
and actual Map read handles round-trips all Automarket payload bytes. Its framework
loader and module inventory are stand-ins; no game or native save is run.

## Private world codec

Reuse inspection: framework `core.lua` at 02a7a6b exposes the cached AoB scanner
and native call bridge, but no PKWARE buffer codec. Map Extensions 1.1.1 at
9d35dfb (`mapextensions/game.lua`, `callbacks.lua`, `handles.lua`) owns wrapped
save/load and ZIP sections. Its API operates on native world state or ZIP data;
it does not provide compression of Recorder's immutable world-section buffers.
Recorder's existing `world-codec.lua`, `world-container.write` and
`codec-worker.new` already own that private-buffer path. Keep their original
game primitives and buffer lifetime; change only their runtime binding here.

Both codec entries now use framework AoB discovery, with shared SHC/Extreme
contexts identifying workspace allocation, failure cleanup, thiscall stack
cleanup and input argument access. Import operands and relative calls are
relocatable. Both sites must resolve uniquely and pass context verification
before either callable is exposed. Resolution runs once; compression batches
and simulation ticks do not scan. No hook, alternate codec, global decoder,
file-hash whitelist or fixed-address fallback is added. Other Recorder fixed
profiles and live acceptance remain unfinished.

Validation: the complete portable suite passes 490 tests (one existing skip),
including relocated bindings on Lua 5.4 and LuaJIT. Each private SHC/Extreme
image resolves both functions and rejects ten missing, ambiguous, modified or
stale-cache cases before exposing any native call. The original-instruction
codec/container/restore harness is also retained and now drives the production
AoB path; its run status is recorded with the PR rather than inferred from these
binding checks.

## Native world header

Framework 02a7a6b and Map Extensions 1.1.1 at 9d35dfb provide no read-only
save-header snapshot API. Map's `getNativeSaveInterface()` wraps inner section
read/write; it does not expose the outer file writer's non-section metadata.
Recorder's existing `world-header.read`, used by `world-capture.capture` and
`freeze`, remains the owner for that snapshot. It now derives all 18 pointers
from five verified writer blocks with framework AoBs, preserving the native
field sizes/order and existing 2141-byte format. No writer or decoder is called,
and Map's hooks remain intact.

The blocks include encoded field sizes and writer argument order; contiguous
operands are cross-checked. Missing, ambiguous, modified or invalid bindings
fail before any header data is read. Resolution runs once. Each snapshot
rechecks the captured instruction context, including decoded pointer operands,
before reading any field. There are no per-tick scans or fixed-address fallbacks.

Validation: 491 portable tests pass (one existing skip), including Lua 5.4 and
LuaJIT with relocated code/data, strict pre-read rejection and no repeat scans.
Each private SHC/Extreme image captures the independently checked 18 fields
byte-for-byte, repeats capture without discovery and rejects 33 invalid-binding
cases. The original-instruction container/restore checks are recorded in the PR;
neither these checks nor signature presence establishes live-match acceptance.

## World section schema

Recorder's `world-layout.decode` is shared by live capture and the validated
disk reader. Map 1.1.1 supplies the native table pointer/count/stride; its owner
does not promise Recorder's complete 122-section replay schema. Inspection of
both native tables confirms identical IDs/order/flags and six size differences
for Extreme's larger pools. Keep that format validation in Recorder's existing
decoder, replacing the two whole-table hash constants with named section
metadata. This is format validation, not an alternative runtime address resolver.

Every ID, size, skip/compression flag, range and the complete zero terminator
must validate before live capture follows any table address. The table comes
only from Map's public interface. A relocated native table is accepted; changed
pool layouts remain unsupported until verified. The hash retained in a capture
is calculated from its actual table for file integrity, not compared to a private
address whitelist. Existing captures keep the same format and validate normally.

The standalone inspector performs bounded descriptor/payload integrity checks
without dereferencing recorded pointers. It no longer treats two exact table
hashes as a compatibility decision. Actual conversion still uses the shared Lua
schema decoder. Other fixed runtime bindings and live acceptance remain work.

Validation: the full portable suite passes 493 tests (one existing skip), plus
the subsequent inspector regression. Lua 5.4/LuaJIT exercise both schemas,
relocation and every descriptor field; the two new decoder tests cover 2444
subtests. Both private native tables match all 122 schema entries, and relocating
every pointer changes only the captured integrity hash. Original-instruction
container/restore and CI results are recorded in the PR.

## Protocol command owner

Protocol 1.1.3 at 175d7a9 adds `getNativeCommandInterface()` to the existing
`protocols/common.lua` / `game/interface.lua` owner. Recorder requires that
version and binds the returned metadata before installing hooks. The handler,
ring, write/current indices, local-player pointer and tick are reused, as is
the existing scheduler callable: no consumer scan or second native call bridge.
The existing replay scope, private payload validation and queue rollback remain
with Recorder. Its history/view/maintenance users share the engine's bindings.
Four address-map entries per game and both write-index offsets are removed.

The inspected Protocol prerequisite changes discovery/API exposure only, so the
Automarket 272-byte format remains unchanged and its adapter recognizes 1.1.3.
Other Recorder native profiles and combined live acceptance remain unfinished.

Validation: 496 portable tests pass (one existing skip), including both Lua
runtimes through the actual Protocol public API with a stand-in native call.
Following the final ring/context reuse, 39 affected tests pass. Original local
SHC/Extreme and the four official EFIGS/Polish fixtures pass 600 SP dispatches,
1200 offline replay dispatches and 600 local captures each, including wrap and
rollback. These execute the original scheduler/selector/dispatcher through the
actual Protocol common/interface/API and Recorder consumer. Protocol's hook
installer, native memory helpers, a test command handler and RPS hook bridges
are stand-ins; this is not physical multiplayer or a live match.

Both native replay-view checks also pass: 24 player-summary cases and all eight
players' resource-book views per game, with identity restored and player/RNG
state unchanged. Pixel drawing is simulated.

## Native RNG state and observers

Recorder 0.50.16 resolves its RNG state and both stream entries once before
installation. The lobby initialization context supplies the state pointer;
its seed setter and both Protocol handler operands are verified. Full stream
bodies establish the 40016-byte state layout, 20000-entry short table, separate
indices, wrap rules and unchanged thiscall/return behavior. Diagnostic detours
retain the original six-byte index loads and recheck both full bodies before
installing either hook. There are no per-tick or per-draw scans.

Reuse inspection: framework `fixes/threading.lua` at 02a7a6b moves the music
timer but exports no RNG state/function API. Legacy `port/o_healer.lua` at
caa50ab derives RNG operands for its own patch; it exports no shared RNG API.
AIC Tactics `config/grace.lua` at e8812c8 resolves its recruitment context;
Recorder cannot depend on a personality module for ordinary recordings. The
existing Recorder observer therefore remains the owner, using framework
`core.AOBScan`/`core.scanForAOB`, decoded operands and `core.detourCode`.
OpenSHC `Random/RNG.hpp` and the original stream instructions confirm layout
and behavior; their reference addresses are confined to tests.

Validation: 498 portable tests pass (one existing skip), including relocation,
negative discovery and late hook conflicts in Lua 5.4/LuaJIT. All six local and
official EFIGS/Polish SHC/Extreme fixtures resolve three bindings, reject 13
negative cases each and make six discovery calls without repeated scans.
Original-instruction tests preserve all RNG bytes/registers with and without
the observer at both index wraps. The actual Protocol/Recorder path also
passes 600 SP dispatches, 1200 offline replay dispatches and 600 local captures
per fixture. Emulator callback/memory/OS boundaries are stand-ins, not live
game or physical multiplayer acceptance. Other native profiles, including
the optional fire/spawn diagnostic contexts, remain unfinished.

## Network and completed-hash observers

Recorder 0.50.17 replaces the three network observer profiles and completed
world-hash site with shared SHC/Extreme instruction contexts. Actor/local-player
and pending-index operands must agree with Protocol 1.1.3's command metadata.
The hash epilogue additionally verifies its Protocol handler, native 12-dword
stride, subtotal store and command-12 send context. Observers retain their
original 5/7/8/11-byte instructions and recheck full preflight guards.

Reuse decision: Protocol `game/hooks.lua` / `game/interface.lua` at 175d7a9 own
the adjacent command-table dispatch patches and scheduler. They do not expose
system-message or completed-native-hash observation callbacks. Recorder's
existing diagnostic callbacks remain the owner of those read-only observations;
no new hook or competing dispatch service is added. The two immediate contexts
end before Protocol's seven-byte patches, and neither overlaps Recorder's
earlier timed-copy/local-capture patches. `hook-check.resolve` shares only the
framework discovery, uniqueness and captured-byte validation already required
by those hooks; it adds no scanner, cache or patch manager.

Validation: 500 portable tests pass (one existing skip). Lua 5.4/LuaJIT cover
relocated contexts, owner disagreement and late conflicts before hooks. Local
SHC 1.41/Extreme 1.41.1-E and all four official EFIGS/Polish fixtures resolve
four sites, reject 23 negative cases each and accept adjacent Protocol patches.
Eight initial discovery calls cover the four contexts; repeated verification
does not scan. All six fixtures also pass 20 original local/remote immediate
command cases through the actual observer callbacks, and 48 native world-hash
observer pairs covering all player slots, all 14 subtotal stores, skip/send
branches and unchanged registers/writes. Transport, memory helpers, the test
command handler, hash callee and UCP callback bridge are stand-ins; physical
transport and live gameplay remain separate acceptance gates.
