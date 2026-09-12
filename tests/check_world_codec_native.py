"""Original PKWARE codec, CRC and CRT copying; only Global memory APIs are stubs.

This optional original-executable check needs pefile in addition to lupa/unicorn.
It does not start or modify a game process.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib
import tempfile
import os
from native_save_fixture import native_save_fixture

from native_image import load_image
from check_executables import image_reader
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as reg
import pefile

def check_codec(path,source_root,variant):
    delta=0 if variant=='SHC' else 0x220
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    load_image(machine, path)
    reader = image_reader(path)
    encode, decode = 0x4724c0 + delta, 0x4725a0 + delta
    assert reader(encode, 6) == bytes.fromhex('83 ec 34 55 56 57')
    assert reader(decode, 5) == bytes.fromhex('83 ec 34 53 56')
    def get(address): return struct.unpack('<I', machine.mem_read(address, 4))[0]
    def put(address, value): machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
    heap, state, source, packed, restored = 0x3500000, 0x3600000, 0x3610000, 0x3630000, 0x3650000
    stack, stop = 0x4108000, 0x3df0000
    allocated = False
    failure = None
    calls = []
    imports = {symbol.name.decode(): symbol.address for entry in pefile.PE(str(path)).DIRECTORY_ENTRY_IMPORT
               for symbol in entry.imports if symbol.name}
    targets = {}
    for index, (name, count) in enumerate([('GlobalAlloc', 2), ('GlobalLock', 1), ('GlobalUnlock', 1), ('GlobalFree', 1)]):
        target = 0x3df1000 + index * 16
        targets[target] = name
        put(imports[name], target)
        machine.mem_write(target, b'\xc2' + struct.pack('<H', count * 4))
    def api(uc, ip, size, context):
        nonlocal allocated
        name = targets[ip]
        calls.append(name)
        sp = uc.reg_read(reg.UC_X86_REG_ESP)
        if name == 'GlobalAlloc':
            assert not allocated and get(sp + 4) == 0x42 and get(sp + 8) == 0x8dd8
            value = 0 if failure == 'allocate' else heap
            if value:
                allocated = True
                uc.mem_write(heap, bytes(0x8dd8))
        else:
            assert allocated and get(sp + 4) == heap
            if name == 'GlobalLock':
                value = 0 if failure == 'lock' else heap
            elif name == 'GlobalFree':
                allocated = False
                value = 0
            else:
                value = 0
        uc.reg_write(reg.UC_X86_REG_EAX, value)
    for target in targets:
        machine.hook_add(UC_HOOK_CODE, api, begin=target, end=target)
    def call(address, *arguments, this=None):
        put(stack, stop)
        for index, argument in enumerate(arguments, 1):
            put(stack + index * 4, argument)
        preserved = {reg.UC_X86_REG_EBX: 0x13579, reg.UC_X86_REG_EBP: 0x24680,
                     reg.UC_X86_REG_ESI: 0x12345, reg.UC_X86_REG_EDI: 0x56789}
        for key, value in preserved.items(): machine.reg_write(key, value)
        machine.reg_write(reg.UC_X86_REG_ECX, state if this is None else this)
        machine.reg_write(reg.UC_X86_REG_ESP, stack)
        machine.emu_start(address, stop, count=4_000_000_000)
        assert machine.reg_read(reg.UC_X86_REG_EIP) == stop, (
            variant,hex(address),arguments,'instruction budget exhausted at',hex(machine.reg_read(reg.UC_X86_REG_EIP)))
        assert machine.reg_read(reg.UC_X86_REG_ESP) == stack + 4 + len(arguments) * 4
        assert all(machine.reg_read(key) == value for key, value in preserved.items())
        assert not allocated
        return machine.reg_read(reg.UC_X86_REG_EAX)
    machine.mem_write(state, struct.pack('<5I', 0, 4096, 0, 0, 0))
    cases = [bytes(1), bytes(32), bytes(4096), bytes(range(256)) * 32,
             b'Crusader replay world\0' * 1000,
             b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(256))]
    outcomes = []
    for data in cases:
        machine.mem_write(source, data)
        machine.mem_write(packed, b'\xa5' * (len(data) + 32))
        machine.mem_write(restored, b'\x5a' * (len(data) + 32))
        put(state + 8, 0xbad); put(state + 16, 0xbad)
        ok = call(encode, state + 8, state + 16, source, packed, len(data))
        assert bytes(machine.mem_read(packed + len(data), 32)) == b'\xa5' * 32
        if ok:
            crc, length = get(state + 8), get(state + 16)
            assert 0 < length <= len(data) and crc == zlib.crc32(data)
            assert call(decode, state + 8, packed, length, restored, len(data)) == 1
            assert bytes(machine.mem_read(restored, len(data))) == data
            assert get(state + 8) == crc
            assert bytes(machine.mem_read(restored + len(data), 32)) == b'\x5a' * 32
            outcomes.append(dict(raw=len(data), compressed=length, crc32=crc))
        else:
            assert get(state + 8) == 0xbad and get(state + 16) == 0xbad
            outcomes.append(dict(raw=len(data), fallback='uncompressed'))
    for failure in ('allocate', 'lock'):
        for address, arguments in ((encode, (state + 8, state + 16, source, packed, 4096)),
                                   (decode, (state + 8, packed, 16, restored, 4096))):
            put(state + 8, 0xbad); put(state + 16, 0xbad)
            assert call(address, *arguments) == 0
            assert get(state + 8) == 0xbad and get(state + 16) == 0xbad
    # Drive the actual Lua wrapper against the same original codec instructions.
    from lupa.lua53 import LuaRuntime
    lua = LuaRuntime(unpack_returned_tuples=True, encoding='latin-1')
    machine.mem_map(0x5000000,0x4000000)
    cursor = 0x5000000
    allocations = {}
    def allocate(size, zero=True):
        nonlocal cursor
        if not allocations: cursor = 0x5000000
        pointer = cursor
        cursor += size + 32
        machine.mem_write(pointer, bytes(size) + b'\xc5' * 32)
        allocations[pointer] = size
        return pointer
    def release(pointer):
        size = allocations.pop(pointer)
        assert bytes(machine.mem_read(pointer + size, 32)) == b'\xc5' * 32
    def expose(address, count, convention):
        assert address in (encode, decode) and count == 6 and convention == 1
        return lambda this, *args: call(address, *args, this=this)
    lua.globals().variant = variant
    lua.globals().nativeSaveFixture=lua.table_from(native_save_fixture(variant))
    lua.globals().source_root = source_root.as_posix()
    lua.globals().allocate = allocate
    lua.globals().release = release
    lua.globals().expose = expose
    lua.globals().readBytes = lambda address, size: lua.table_from(list(machine.mem_read(address, size)))
    lua.globals().readString = lambda address, size: bytes(machine.mem_read(address, size))
    # Match the shipped RPS C-string writer, including truncation at embedded NUL.
    lua.globals().writeString = lambda address, data: machine.mem_write(address, data.encode('latin-1').split(b'\0')[0]+b'\0')
    lua.globals().writeBytes = lambda address, data: machine.mem_write(address, bytes(data[i] for i in range(1,len(data)+1)))
    lua.globals().readInteger = get
    lua.globals().writeInteger = put
    lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/native']={profile={name=variant}}
modules={['map-extensions']={getNativeSaveInterface=function() return nativeSaveFixture end}}
package.loaded['code/native-hash']={prepare=function() end}
core={allocate=allocate,deallocate=release,exposeCode=expose,readBytes=readBytes,
 readString=readString,writeString=writeString,writeBytes=writeBytes,readInteger=readInteger,writeInteger=writeInteger}
codec=require('code/world-codec')
function encodeSection(data)
 return codec.withBuffers(#data,function(work) retained=work; return work:compress(data) end)
end
''')
    failure = None
    for diagnostics in (False,True):
        lua.execute("require('code/build-profile').diagnostics="+str(diagnostics).lower())
        for data in cases:
            encoded = lua.globals().encodeSection(data)
            assert not allocations
            assert not lua.eval("pcall(function() retained:compress('x') end)")[0]
            if encoded is not None:
                encoded = encoded.encode('latin-1')
                raw_size, packed_size, crc = struct.unpack_from('<3I', encoded)
                assert raw_size == len(data) and packed_size == len(encoded) - 12 and crc == zlib.crc32(data)
                machine.mem_write(packed, encoded[12:])
                assert call(decode, state + 8, packed, packed_size, restored, raw_size) == 1
                assert bytes(machine.mem_read(restored, raw_size)) == data
    lua.execute("assert(not pcall(function() codec.withBuffers(64,function() error('injected') end) end))")
    assert not allocations
    # Drive the complete capture -> validated reader -> native container path on
    # the original 122-entry layout. Static image/BSS data is a format fixture,
    # not a playable match. Decode every resulting payload with the native codec.
    with tempfile.TemporaryDirectory(prefix='native world ') as temporary:
        folder=Path(temporary)
        virtual='ucp/multiplayer-recordings/native-world-test'
        def disk(path):
            assert path.startswith(virtual+'/')
            return folder/path[len(virtual)+1:]
        def convert(value):
            if hasattr(value,'items'):
                keys=list(value.keys())
                if keys and all(isinstance(k,int) for k in keys):
                    return [convert(value[i]) for i in range(1,len(keys)+1)]
                return {k:convert(v) for k,v in value.items()}
            return value
        g=lua.globals()
        g.test_folder=folder.as_posix(); g.virtual_path=virtual
        g.executable_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        g.readByte=lambda a:machine.mem_read(a,1)[0]
        g.hash_data=lambda data:hashlib.sha256(data.encode('latin-1')).hexdigest()
        g.encode_json=lambda data:json.dumps(convert(data),separators=(',',':'))
        g.decode_json=lambda data:lua.table_from(json.loads(data),recursive=True)
        g.replace_file=lambda old,new:os.replace(disk(old),disk(new))
        game=0x1fe7d10 if variant=='SHC' else 0x2a7b210
        put(game+12,20); g.game_core=game
        lua.execute('''
local original=io.open
io.open=function(path,mode)
 if path:sub(1,#virtual_path)==virtual_path then path=test_folder..path:sub(#virtual_path+1) end
 return original(path,mode)
end
json={encode=function(_,v) return encode_json(v) end,decode=function(_,v) return decode_json(v) end}
sha={sha256=hash_data}; core.readByte=readByte
require('code/native').profile.sha256=executable_hash
require('code/native-hash').sha256=hash_data
require('code/native-hash').file=function(path,limit,onChunk,onProgress)
 local data=require('code/world-reader').read(path,limit)
 if onChunk then onChunk(data,#data) end
 if onProgress then onProgress(#data) end
 return hash_data(data)
end
package.loaded['code/platform']={replace=replace_file}
engine={sites={gameCore=game_core},singlePlayer=function() return true end,
 tick=function() return 1 end,networkState=function() return {mode=1} end,
 rngData=function() return string.rep('r',0x9c50) end,resourceState=function() return {} end}
settings={raw='settings',hash=sha.sha256('settings'),environment='{}',environmentHash=sha.sha256('{}')}
capture=require('code/capture-files').begin(virtual_path,engine,settings)
assert(capture.world.status=='complete',capture.world.reason)
prepared=require('code/world-container').prepare(virtual_path,engine)
''')
        assert not allocations
        container=(folder/'world-native.sav').read_bytes()
        # Execute the actual native worker entry with the original compressor.
        # Thread scheduling is simulated; game memory is poisoned after freeze.
        pending_worker=[]
        def create_thread(_, stack_size, entry, job, flags, thread_id):
            pending_worker.append((entry,job)); return 99
        def wait_thread(handle,timeout):
            assert handle==99 and timeout==0
            if pending_worker:
                entry,job=pending_worker.pop(); call(entry,job)
            return 0
        lua.globals().create_thread=create_thread
        lua.globals().wait_thread=wait_thread
        lua.globals().copy_memory=lambda target,source,size:machine.mem_write(target,bytes(machine.mem_read(source,size)))
        lua.execute('''
core.allocateCode=function() return 0x3de0000 end; core.writeCode=writeBytes; core.copyMemory=copy_memory
require('code/platform').stdcall=function(_,name)
 if name=='CreateThread' then return create_thread end
 if name=='WaitForSingleObject' then return wait_thread end
 return function() return 1 end
end
engine.commandsPending=function() return false end
engine.singlePlayer=function() return false end
engine.networkState=function() return {mode=1,syncStatus=0} end
require('code/build-profile').diagnostics=false
frozen=require('code/world-capture').freeze(engine)
''')
        first=lua.eval('frozen.entries[1]')
        address,size=first.address,first.size
        before=bytes(machine.mem_read(address,size))
        machine.mem_write(address,b'\xa5'*size)
        game_writes=[]
        hook=machine.hook_add(UC_HOOK_MEM_WRITE,
            lambda uc,access,address,size,value,user:game_writes.append((address,size)) if address<heap else None)
        try:
            lua.execute("assert(frozen:ready()); frozen:write(virtual_path..'/frozen.sav'); frozen:close()")
        finally:
            machine.hook_del(hook); machine.mem_write(address,before)
        assert not game_writes,game_writes[:10]
        assert not allocations
        assert (folder/'frozen.sav').read_bytes()==container
        print(f'PASS: {variant} native worker restores identical container from frozen memory after original section mutation',flush=True)
        def decode_block(block):
            length,compressed,crc=struct.unpack_from('<3I',block)
            assert compressed==len(block)-12 and 0<length<=32*1024*1024
            encoded=allocate(compressed); output=allocate(length)
            try:
                machine.mem_write(encoded,block[12:])
                assert call(decode,state+8,encoded,compressed,output,length)==1
                data=bytes(machine.mem_read(output,length))
                assert get(state+8)==crc==zlib.crc32(data)
                return data
            finally:
                release(output); release(encoded)
        assert struct.unpack_from('<I',container)[0]==0xffffffff
        offset=4; blocks=[]
        while True:
            size=struct.unpack_from('<I',container,offset)[0]; offset+=4
            if not size: break
            blocks.append(container[offset:offset+size]); offset+=size
        assert len(blocks)==6 and decode_block(blocks[0])==bytes(40512)
        metadata=(folder/'world-header.bin').read_bytes()
        assert blocks[1][:8]+decode_block(blocks[1][8:])==metadata[:1008]
        assert b''.join(blocks[2:])==metadata[1008:]
        directory=container[offset:offset+3036]; payload=container[offset+3036:]
        assert struct.unpack_from('<4I',directory)==(3036,len(payload),122,172)
        manifest=json.loads((folder/'world.json').read_text())
        with (folder/'world.bin').open('rb') as source_file:
            for i,entry in enumerate(manifest['sections']):
                raw_size,packed_size,section,compressed,start=[struct.unpack_from('<I',directory,32+array*600+i*4)[0] for array in range(5)]
                assert section==entry['section'] and raw_size==entry['size']
                data=payload[start:start+packed_size]
                if compressed: data=decode_block(data)
                assert data==source_file.read(raw_size), (variant,section)
        assert not allocations
        print(f'PASS: {variant} all 122 native world sections and header round-trip through the actual Lua container and original codec',flush=True)
        from check_world_load_native import check_world_load
        check_world_load(machine, folder, variant, call, imports)
    report=dict(variant=variant,cases=outcomes,actualLuaWrapper=True,buffersReleased=True,
        allocationAndLockFailure=True,abi=True,liveGame=False)
    print(f'PASS: {variant} original PKWARE primitives and actual Lua codec, round trips, failure cleanup and ABI',flush=True)
    return report
