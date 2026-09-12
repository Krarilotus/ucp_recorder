# Multiplayer starting-world capture and native file conversion

This stage preserves the native world at the first simulation callback and makes
host/client starting differences inspectable. **It does not restore multiplayer
games offline, and these captures remain outside the playable replay browser.**

## Why not call the existing single-player save adapter?

The original `FilePackager::writeMapOrSaveFile` (SHC `0x474480`, Extreme
`0x4746B0`) sends periodic synchronization messages every ten sections in
multiplayer. It also updates `GameCore.gameDuration` from wall time, allocates
temporary buffers, updates FilePackager state and renders a minimap. Disabling
its progress callback would not remove those other effects. The existing
single-player guard remains in place.

The implementation already present in OpenSHC at
`src/OpenSHC/IO/FilePackager/writeMapOrSaveFile.cpp`, the corresponding Ghidra
disassembly, and the original executable data tables establish the layout.
No replacement of that already implemented OpenSHC function is needed.

## Captured data

`world-capture.lua` reads the original `MapSectionAddress` table exposed by
Map Extensions 1.1.1, validates every section against `world-sections.lua`,
and only then dereferences its entries. Each descriptor has a
32-bit address, skip field and size, followed by 16-bit compression and section
fields. Both verified tables contain 122 sections followed by a zero terminator.
The six Extreme size differences are explicit; addresses are discovered by Map,
not constrained to a private table fingerprint. The addresses below identify
the research fixtures only.

| Variant | Descriptor table | Table bytes | World bytes |
| --- | --- | --- | --- |
| SHC 1.41 | `0xB92A58` | 1968 | 13,776,465 |
| Extreme 1.41 | `0xB92BE8` | 1968 | 25,168,385 |

`world.bin` concatenates the uncompressed section bytes. `world-layout.bin`
preserves the checked descriptors. `world.json` records tick, executable,
offsets, section sizes and individual SHA-256 values. Memory reads and writes to
disk use at most 64 KiB per chunk; hashing temporarily assembles one section
(up to 11,680,000 bytes in Extreme). A final tick check rejects advancement
during the capture. There are no native game-memory writes or native save calls.

The synchronous operation can delay the first frame and network polling; its
runtime cost still needs measurement on both physical PCs. Read-only does not
mean zero timing overhead or establish thread-level snapshot isolation.

Version 0.37.1 uses Windows CryptoAPI SHA-256 for the large section payloads.
UCP already imports Advapi32 for its own hashing/signature checks. The recorder
uses an ephemeral provider context (no stored keys), a reusable 64 KiB scratch
buffer, explicit byte lengths, and releases hash/provider handles on errors too.
A binary-string probe and the SHA-256 `abc` vector reject an incompatible bridge
before capture. Small descriptors/manifests still use UCP's normal SHA-256.

An isolated Lua 5.3 benchmark of 25,168,385 bytes on the development PC took
4.70 seconds through the shipped pure-Lua implementation and 0.039 seconds
through CryptoAPI. This used a 64-bit Python address adapter and private buffers;
it is not an in-game 32-bit frame/network measurement. Windows CI additionally
checks actual CryptoAPI vectors, while x86 emulation checks the stdcall bridge.
See Microsoft's [CryptHashData contract](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-crypthashdata).

Automarket 1.1.0 keeps additional state in its exposed `pAutomarketData` allocation.
`automarket.bin` copies precisely the version-2, 2416-byte payload used by its
map-extensions serialization callback: header, nine settings slots, credit and
fees. Slot zero is local editing state and may differ between peers. The adapter
requires the reviewed extension versions and checks the saved-layout version.
It does not call arbitrary extension serialization callbacks.

map-extensions 1.0.0 maintains a replacement table with a custom ZIP section.
Its before-save callback runs registered serializers, changes custom native
section metadata and writes a cache ZIP. Reading the original native table
does **not** capture that replacement section. Only Automarket is handled
explicitly here; coverage of other extensions' dynamic state remains open.

## Integrity, copying and failures

A failed table check, memory read or world write records `world.status=failed`
and its reason in `capture.json`. The status dialog reports the missing start
state. Command persistence continues; an incomplete world file is not accepted
as complete evidence. Successful world manifests are committed by replacement
and their hash is stored in the parent capture manifest. Named capture copies
include all completed world files and Automarket data.

```text
python tools/inspect_replay.py multiplayer CAPTURE_FOLDER
python tools/inspect_replay.py compare-worlds HOST_FOLDER CLIENT_FOLDER
```

Inspection checks the recorded table's integrity hash, bounded descriptors, descriptor-to-manifest agreement,
exact file length and every section hash. Comparison requires matching variant
and capture tick and reports each differing section's first byte address.
These are investigation leads: native sections include presentation state and
padding, while omitted extension state cannot be validated through these hashes.

## Native header and file conversion (0.41.0)

New captures include `world-header.bin`: 2,141 bytes of description, cached
time/hash, player, scenario and Skirmish metadata absent from the 122 sections.
`world-header.lua` verifies all 18 native writer argument references before
reading any field. The world manifest hashes these bytes and describes their
five groups. Cached time/hash fields are preserved as native metadata; they are
not reported as fresh measurements of the captured tick. The actual simulation
tick remains part of the section data.

`world-layout.lua` owns descriptor decoding. Capture owns live memory access;
`world-reader.lua` owns bounded disk reads and integrity validation. The reader
checks the capture identity, executable, manifest hash, original descriptor
table, exact section metadata, header and each payload before conversion.
Old captures without the header remain inspectable, but need a new recording
for native conversion.

`world-container.prepare(path, engine)` can run only at the single-player
Skirmish menu. It builds `world-native.sav` and a hashed `world-native.json`
descriptor, without entering a match or writing game world/transport state.
Conversion is an internal prerequisite, not a new Play button or a supported
way to load multiplayer captures through the ordinary save menu.

The writer uses the game's existing PKWARE `DecoderState::doImplode` and
`doExplode` with a private decoder and scoped buffers. It checks compression
status, CRC and full byte equality by decoding each result, falling back to
raw section storage when compression gives no benefit. It never invokes the
live multiplayer save routine or borrows its global decoder state. The complete
stored payload must fit the original loader's 6,000,000-byte allocation.

The native header requires a nonzero preview block to reach the following
metadata. Conversion supplies an explicitly neutral 200-by-200 indexed preview;
it does not render the current world or claim a recorded map thumbnail.
Automarket's captured payload is encoded as
`automarket/automarketplayerdata.bin` using map-extensions' existing MemoryZip
library in custom section 1337. Current-game serializers are not called.
An isolated Windows check uses the shipped x86 Lua and MemoryZip DLLs plus the
actual map-extensions read handle, then verifies the resulting ZIP bytes with
.NET's independent ZIP reader. The UCP library-loader bridge is a stand-in;
the actual map-extensions loading wrapper still needs integration verification.

Temporary output is validated before replacing a previous prepared file.
Conversion failures preserve the original capture. Both capture and prepared
metadata continue to state `playable=false`.

The optional original-executable check runs the actual Lua capture, reader,
container and codec against both supported executables. It independently
decodes every stored section, then runs the original FilePackager reader with
all section destinations overwritten first. File, heap, clock, resource-name
and audio calls are simulated; directory parsing, initialization, decompression,
section routing and native completion execute original instructions. This is
a static format fixture, not a playable match or an outer UI/network test.

```text
python -m pip install pefile
python tests/check_executables.py "PATH/TO/ORIGINAL/GAME" --world-container
```

On Windows, the shipped-library adapter check also runs without a game process:

```powershell
C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/check_automarket_zip_windows.ps1 -GameDirectory "PATH/TO/INSTALLED/UCP/GAME"
```

This requires the installed `lua.dll` and `map-extensions-1.0.0.zip`. The policy
flag applies only to that test process. It does not change machine policy.

## Remaining restoration work

The original section table excludes runtime networking fields. For example,
the active mode, eight transport IDs and resolved command actor are not saved;
the saved mode copy (section 1106), AI slots (1100) and local player (1051) are.
`capture.json.initialNetwork` preserves observed identities separately, but
does not yet implement their offline meaning.

The capture must also preserve/reproduce immediate and system events, and must
take replacement-world snapshots at verified resynchronization boundaries.
Until those gates pass, another long live game is not an offline replay test.
