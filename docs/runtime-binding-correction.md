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

## Native maintenance/replay phases

Recorder 0.50.18 derives the game-state pointer and coordinator entry from the
original main-loop call between Protocol's command-processing and receive
calls. The surrounding handler operands must match Protocol. Maintenance and
world phases are validated inside that resolved function, with repeated tile
operands checked and the world-update callee decoded and verified. The two
existing hooks retain their five/seven-byte spans. Both phase guards, caller
and world callee are rechecked before allocating/installing the phase runner.

Reuse inspection: framework `hooks.lua` at 02a7a6b exposes `afterInit`, not the
maintenance-only/unclocked-world phases. Protocol 175d7a9 owns commands rather
than those phases. Existing Recorder `maintenance-native.runner` and
`scoped-code` therefore remain the execution owners; they still enter the
original coordinator and its existing subsystem calls. No Lua timer, added
polling, duplicated game update or new hook is introduced.

The maintenance-call sequence alone was not unique in the executable. Its
binding instead comes from the uniquely verified main-loop caller and decoded
coordinator, with full phase context at the confirmed instruction offsets.
This requires two discovery calls including the uniqueness check, once per
initialization. Both variants have the same coordinator instruction layout;
their distinct world-state fields remain inside the original native callee.

Validation: 502 portable tests pass (one existing skip). Both Lua runtimes
exercise relocated caller/coordinator/callee addresses and strict failure
before writes. All six local/official SHC 1.41 and Extreme 1.41.1-E images pass
four bindings and 15 negative cases each. Each also executes 77 original
coordinator cases through the production phase binding, covering passive
recording, viewer pause, halt, maintenance-only and unclocked world replay,
native navigation countdown/reset, unchanged match clock and restored pause.
Other subsystem callees are observable stand-ins; this is not a full match.

## Engine command hooks

Recorder 0.50.19 replaces seven fixed hook entries and three variant-specific
command offsets with Protocol 1.1.4 metadata and decoded native contexts.
Protocol `game/interface.lua` at 10001be already resolves queue/scheduler entries;
its public API now exposes those entries and their captured 69/79-byte guards.
The guards are immutable strings because the framework's nested table proxy
does not implement array length. Recorder materializes them locally for its
existing `hook-check` validation; it does not copy Protocol's signatures or scan
those functions again.

The maintenance binding's existing main-loop caller supplies the dispatcher.
Recorder verifies its original selection call, payload-copy contexts and
completed-dispatch tail. Decoded actor, selection, count, tick and write-index
operands must agree with Protocol and the confirmed native layout. The seven
existing 5/6/8/10-byte hook spans retain their displaced instructions and
existing callbacks. All captured guards are checked before installation,
including both owner entry contexts. The dispatcher context ends before
Protocol's adjacent seven-byte patch; no hook or dispatch service is added.
There are only two consumer discovery calls, belonging to the already shared
maintenance caller, and none during command processing.

Validation: 504 portable tests pass (one existing skip), including relocated
owner/context checks in both Lua 5.4 and LuaJIT. All
six local/official EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E fixtures resolve
ten bindings, reject 24 invalid/late-change cases each and accept Protocol's
adjacent patch through the actual framework extension proxy. Each fixture also
passes 600 original SP dispatches, 1200 offline replay dispatches and 600 local
captures through the production binding, including ring wrap and rollback.
Native bridge, transport, memory-helper and test-command boundaries remain
stand-ins. Other engine/native profiles and full live acceptance are unfinished.

## Coordinator state and calendar

Recorder 0.50.20 derives tick entry/return/admission, halting-menu query,
GameCore/pause/menu-input state and navigation countdown from its existing
maintenance caller/coordinator binding. Protocol's command metadata and
Recorder's RNG owner validate the repeated state operands and native calls.
Only the native calendar setter needs another framework lookup; its field
relationships yield the month/year address relative to the resolved game state.
The six context records and four state pointers replace both fixed engine
profiles. History, replay UI and overlay input reuse the resolved GameCore
current-view field, removing that entry from `native.lua` too.

Reuse inspection: UI `ui/game.lua` and `manager/init.lua` at c373343 export
rendering/menu objects, not GameCore, native clock admission or the calendar.
Map `mapextensions/game.lua` at 9d35dfb exports save entries/table, not these
simulation phases. Framework `hooks.lua` at 02a7a6b exposes initialization.
Recorder therefore retains its existing phase/gate ownership and uses
`hook-check.context/resolve`. OpenSHC `GameStateStructures/processGameTick.cpp`
and original instructions establish the original order and ABI. No native
update is reimplemented and no hook, poller or per-tick lookup is added.

The tick entry/admission/returned hooks retain their 7/5/5-byte spans and the
original return path. Full contexts are rechecked before engine construction,
before Recorder's own later scope/phase patches alter those contexts. The
navigation reset immediate is deliberately variable: unchanged Legacy
`o_increase_path_update_tick_rate` changes 200 to 50. Repeated countdown
operands still must agree; both settings execute the game's original code.

Validation: 506 portable tests pass (one existing skip); the final menu-view
reuse passes 44 affected tests. Both Lua runtimes cover relocated addresses,
missing/ambiguous contexts and late conflicts. All six local/official
EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E images pass ten bindings, 33 negative
cases and the Legacy period case each. Each also passes 77 original coordinator
cases through these bindings and 600 SP/1200 offline replay dispatches plus
600 local captures. Protocol metadata is a fixture in the coordinator runner
and the real owner in the binding/dispatch tests. Other native callees, bridges
and transport remain stand-ins; live gameplay, save/replay and physical
multiplayer acceptance are still outstanding.

## Loading and match transitions

Recorder 0.50.21 replaces its remaining five fixed lifecycle hooks with named
bindings. RNG's existing initialization context supplies match start and the
adjacent preparation tail. UI 1.0.2 `getNativeMenuInterface()` at af31ceb supplies
the existing transition entry and captured guard; its receiver must agree with
the resolved GameCore. There is no second menu-transition lookup or dispatcher.

The outer load handler supplies its action branch and completion epilogue by
relative-target decoding. The reset path must call that same finalization owner
and UI's transition entry. Its short cleanup sequence was ambiguous, so the
identifying context includes the preceding menu-action branch. Native resource
filename access comes from Map 1.1.1's already wrapped reader, with its internal
call and 1001-byte filename layout verified. The map-name leaf has its own
complete identifying context. World-read completion must lie inside the Map
reader and refer to GameCore's saved duration fields.

Map `mapextensions/game.lua` at 9d35dfb calls `afterReadSav` after the native
reader returns, including its early failure exits; that callback alone does
not establish a successful read. Recorder retains its existing successful-tail
observer and outer-load lifecycle instead of treating a failed read as a new
world. Hook spans and load/filename behavior are unchanged. All guards run
before engine construction and Recorder's later scope/phase patches. Four
initial lookups plus uniqueness checks resolve the remaining contexts; repeated
loads and menu transitions add no scans.

All obsolete `native.addr` mappings and callers are removed. The old layout is
now only an explicit research fixture. The original header identity gate stays
temporarily because history/scoped/result profiles still need migration; its
reference hash is not yet the final executable identity implementation. The
obsolete switch/parameter-buffer guards are removed: the actual UI and Protocol
owners now validate those bindings.

Validation: 508 portable tests pass (one existing skip), including relocated
Lua 5.4/LuaJIT lifecycle/owner and failure checks.
All six local/official EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E images pass
11 bindings, 46 rejection cases each and Map's adjacent entry-wrapper case.
Each also executes 148 original load failure/completion/identity cases through
the production binding, plus 600 SP/1200 offline replay dispatches and 600 local
captures. UI/Protocol initialization and framework proxy/extraction are real
in binding tests; Map ABI metadata, OS/transport, native bridge and selected
callees are fixtures. Full installed game, save/replay and physical multiplayer
acceptance are still required.

## Results and player resources

Recorder 0.50.22 removes the last production `engine-sites` profile and the
statistics/insertion address tables. `result-sites` uses three framework AoB
lookups plus uniqueness checks: the results timer, building resource recount,
and complete SKMasters insertion routine. The insertion's CALL supplies the
native packer, whose CALL supplies the native scorer. Complete instruction
contexts, unrolled player reads/writes, record strides, capacities and relative
targets are checked before any Recorder patch is installed. Subsequent calls
use the retained bindings; there is no per-tick discovery.

Reuse inspection: UI 1.0.2 `getNativeMenuInterface` at af31ceb owns the transition
entry; Protocol 1.1.4 at 10001be owns the local-player field. Both must agree
with the timer/packer. Map 1.1.1 `mapextensions/game.lua` at 9d35dfb exposes save
entries and section descriptors, not result packing or insertion observers.
Recorder already owns these observers and bounded snapshots. OpenSHC's
`Game/Skirmish.func.hpp`, `IO/SkMasterDataEntry.hpp` and the original instructions
establish the cdecl ABI and layouts; no OpenSHC reference address is used at
runtime. Legacy source and the native score, insertion, recount and victory
logic remain unchanged. No hook or native-call bridge is added.

Validation: 510 portable tests pass (one existing skip), including both Lua
runtimes with relocated owners and context/operand/conflict rejection. All six
local/official EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E images pass the 14
bindings, 19 missing/ambiguous/stale/occupied checks each, 192 original/patched
result-timer cases, four native insertion/eviction/rejection cases, 18 native
packer/score cases and nine resource-recount cases. The packer uses the native
scorer and bounded copies; only its OS date call is stubbed. Timer UI callees,
insertion disk output, module bridges and transport remain stand-ins. Private
image scan timings are not game-performance measurements.
The native dispatch harness also uses these production engine bindings for
600 SP/1200 offline replay dispatches and 600 local captures per image.

History and scoped/offline/optional RNG bindings and the temporary executable
identity gate still need correction. This is component evidence, not an
installed-game, whole-world save/replay or physical multiplayer acceptance.

## Native battle-history bindings

Recorder 0.50.23 replaces the history profile with two unique framework AoB
contexts: preparation and rendering. The adjacent action handler, native sorter,
row and hover contexts are validated before their field operands are decoded.
All ten native index/record references must agree with the result-storage owner;
count, scroll, sort and saved-mode references are checked across preparation,
actions, sorting and rendering. Full action control-flow displacements retain
their native meaning. No additional hook, renderer, list store or polling is added.

UI 1.0.2 at af31ceb was inspected again: `manager.lookupMenu` owns menu item
lookup and reallocation, and `UI.MenuView` constructs views. Neither exposes
native history preparation/actions or their private catalogue operands. Recorder
therefore keeps its existing history data-source adapter, UI menu/overlay APIs,
and native rendering/actions. It reuses `result-sites` for stored records and
statistics, Protocol for mode, and the existing UI entry for results/return.
The obsolete fixed history table is now only a test fixture.

512 portable tests pass (one existing skip). Both Lua runtimes exercise relocated contexts, repeated owner fields, absence,
ambiguity and pre-/post-resolution conflicts. All six local/official EFIGS/Polish
SHC 1.41 and Extreme 1.41.1-E fixtures pass 22 bindings and 28 rejection checks
each. Disassembly of the entire native action/renderer confirms all data-source
references are covered. Original packer, score and date-copy instructions execute
with writes confined to the temporary entry and stack; only Windows GetLocalTime
is substituted. These checks do not establish installed GUI interaction or live
save/replay acceptance. Scoped/offline/optional RNG bindings and the temporary
identity gate remain unfinished.

## Offline replay transport and pacing

Recorder 0.50.24 removes `offline-sites`' fixed variants and calculated address
deltas. Map 1.1.1's wrapped writer supplies its internal save-pacing context and
synchronization worker; that worker supplies both packet/message senders.
Protocol 1.1.4's queue supplies both validated transmit calls. Recorder's existing
coordinator binding retains its decoded receive entry before the returned-tick
hook changes the preceding instruction. The halting-menu guard is reused from
the existing engine-state owner. Four framework lookups resolve the remaining
pacing, autosave, polling and lag contexts.

This follows inspection of `mapextensions/game.lua` at 9d35dfb, Protocol
`game/interface.lua`/common command bindings at 10001be, and Recorder's current
phase, command and offline consumers. No owner exposes a separate transport
isolation service; Recorder keeps its existing passive offline gates. Complete
contexts and repeated clock/mode/queue operands must agree before installation.
The transport caller context begins after Recorder's timed-command hook, so
opening a replay later does not mistake Recorder's own patch for a conflict.
There is no new hook, temporary global mode swap or per-tick scan.

514 portable tests pass (one existing skip). All six local/official EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E images pass ten
bindings, 36 rejection checks, both prior-Recorder-hook cases, 60 original/passive/
active instruction-gate cases and 64 original save-pacing branch cases each.
The save branch suppresses synchronization only while offline, preserving mode.
Relocated Lua 5.4/LuaJIT checks also cover all owner-field relationships and
installation failure/idempotence. OS, network, module bridges and selected
callees remain fixtures; these are not live multiplayer/replay acceptance.

## Replay scope callers

Recorder 0.50.25 replaces the scoped hook table with 16 unique framework AoB
contexts. They identify the existing presentation RNG calls, native wedding and
taunt selection, head placement, dust and mother gates. Each RNG root and call
target must agree with `rng-bindings`; player, mode, tick and core operands must
agree with Protocol and the existing game-state owner. The seven mood-music calls
are checked within their complete native function. Dust retains its decoded
native allocator and verified callee-cleanup ABI.

The existing engine-state resolver supplies both pause gates, and the RNG owner
supplies the optional seed wrapper. Its patch span is checked only when fixed
seed is enabled. General RNG identification still checks the wrapper identity;
an occupied disabled seed hook does not disable unrelated scope binding.
RNG verification now shares `hook-check` instead of a second context/scanner
helper. No emitter, hook count, RNG implementation or per-tick work is added.

This follows inspection of Recorder's `fixes`, `scoped-code`, `engine-state-sites`
and `rng-bindings` consumers at be4e634, Protocol 1.1.4 at 10001be and UI 1.0.2 at
af31ceb. Scope remains Recorder-owned; the existing command/state/RNG owners
supply shared identities. Reference addresses remain only in test fixtures.

517 portable tests pass (one existing skip), including relocated bindings and
owner disagreement in Lua 5.4 and LuaJIT. All six local/official EFIGS/Polish SHC
1.41 and Extreme 1.41.1-E images pass 28 bindings, 104 rejection checks, both seed
option cases, 224 passive gate comparisons, complete audio-caller inventories,
56 native head-placement, 110 native taunt and 288 native wedding cases each.
The 32 discovery calls occur once; 100 cached verifications add no scans.
Native callees are executed where stated; gate helper callees, OS/transport and
module bridges remain fixtures. Optional fire/spawn attribution bindings and the
temporary identity gate remain unfinished. This is component evidence, not a
live game, whole-world save/replay, physical multiplayer or performance claim.

## Optional RNG caller attribution

Recorder 0.50.26 replaces the last fixed fire/spawn caller tables. Three unique
framework AoB contexts identify the native entry and RNG call, validate the
saved-register/argument layout and agree with the existing RNG owner. Spawn also
checks native capacity (2500 or 10000), paired capacity bounds and Protocol's
clock/tag fields. Both fire callers must share coordinate and tile tables.
The short fire entry was ambiguous in the actual executables; its identifying
context includes the subsequent native admission logic. No game code is copied.

The inspected owner and consumer are Recorder's `rng-observer` and
`rng-attribution` at c9dc055. Attribution still reads stacks at that observer's
existing two stream hooks; these optional bindings install no hook and perform
no writes. They resolve lazily once when diagnostics starts and recheck current
contexts on a later attempt. Cached RNG identity remains usable after Recorder
has installed its own observer. A rejected optional context disables that part
of diagnostics, preserving the match and existing diagnostic limits.

519 portable tests pass (one existing skip). Lua 5.4 and LuaJIT cover relocated
callers, both capacity layouts and owner/context disagreement. All six native
SHC/Extreme local/EFIGS/Polish fixtures pass three callers, 32 rejection cases,
two prior-observer-hook cases and 100 cached accesses without additional scans.
Original native prologues establish the read-only argument layout: four fire
cases without callee stubs and one spawn case with `setUnitValues` stubbed.
The temporary executable identity gate remains to be replaced after the final
binding inventory. These checks do not establish live game acceptance.

## Framework identity and shared context verification

Recorder 0.50.27 removes the temporary PE-header gate and both hardcoded
executable hashes. `data.version` supplies the game family and 1.41 version,
using the actual framework parser available in the module environment. Every
native capability remains checked by its owner. The existing `platform.identity`
and `native-hash.file` supply the running executable's SHA-256 for recordings.
It is no longer selected from reference hashes or used to select addresses.
The existing recorded-executable comparison remains unchanged.

Inspected framework revision 02a7a6b: `main.lua` includes `data` in `moduleEnv`;
`data/version.lua` provides `getGameVersionMajor`, `getGameVersionMinor` and
`isExtreme`. Recorder's existing Windows path/native hash service is reused.
This adds no scan, hook, DLL service or per-tick hash. UI, save-header and codec
bindings now share the existing `hook-check.resolve/context` helper, removing
their duplicated scanner/uniqueness/context implementations without changing
their native owners, signatures, ABI or discovery counts.

The final production literal-pointer inventory contains no fixed executable
address or RVA fallback. Remaining large constants are integer limits, encoding
multipliers, OS flags, colors, sizes and verified structure offsets. Native
layout schemas retain field sizes and section identity; they obtain pointers
from Map's runtime descriptors. Reference addresses/hashes remain test evidence.
This inventory does not substitute for the combined-module architecture and
installed-game acceptance review.

All six local/official EFIGS/Polish SHC 1.41 and Extreme 1.41.1-E images pass the
actual framework parser and restricted module environment, plus 29 UI, two codec
and 18 header bindings with 34/10/33 rejection cases. That parser check substitutes
the OS path/hash boundary. Separately, the real 32-bit Lua/RPS/CFFI console passed
the production path/hash bridge against its independently measured executable
SHA-256, plus existing binary-transfer and SHA-256 checks. Neither test launches
the game. Combined startup, physical multiplayer, save/replay and measured game
performance remain outstanding.

The complete portable suite passes: 519 tests, one existing skip and 6411
subtests. Unsupported framework versions, failed file reads and malformed
digests clear any previous identity before hook installation.
