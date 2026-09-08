# Read-only multiplayer starting-world evidence (0.37.0)

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

`world-capture.lua` reads the original `MapSectionAddress` table, verifies its
entire SHA-256, and only then dereferences its entries. Each descriptor has a
32-bit address, skip field and size, followed by 16-bit compression and section
fields. Both verified tables contain 122 sections followed by a terminator.

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

Inspection checks the original table hash, descriptor-to-manifest agreement,
exact file length and every section hash. Comparison requires matching variant
and capture tick and reports each differing section's first byte address.
These are investigation leads: native sections include presentation state and
padding, while omitted extension state cannot be validated through these hashes.

## Remaining restoration work

These raw bytes are not a native `.sav`. Native container metadata, load-time
fixups and extension restoration still need a checked conversion/restore path.
The original section table also excludes runtime networking fields. For example,
the active mode, eight transport IDs and resolved command actor are not saved;
the saved mode copy (section 1106), AI slots (1100) and local player (1051) are.
`capture.json.initialNetwork` preserves observed identities separately, but
does not yet implement their offline meaning.

The capture must also preserve/reproduce immediate and system events, and must
take replacement-world snapshots at verified resynchronization boundaries.
Until those gates pass, another long live game is not an offline replay test.
