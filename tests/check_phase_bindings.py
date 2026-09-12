"""Original coordinator phase contexts and negative bindings; no game."""
import hashlib
from pathlib import Path
import re
import struct
import pefile
from lupa.lua54 import LuaRuntime
from native_command_fixture import native_command_fixture


def check(path,variant):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes();pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase;image=bytearray(pe.get_memory_mapped_image())
    matches={};scans=[];writes=[]
    def read(a,n):
        assert base<=a and a+n<=base+len(image),hex(a)
        return bytes(image[a-base:a-base+n])
    def scan(pattern,start=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:],re.DOTALL)
        address=base+offset+found.start() if found else 0
        if start is None:matches[pattern]=address
        return address
    def fixture(first=scan,second=scan):
        lua=LuaRuntime(unpack_returned_tuples=True)
        g=lua.globals();g.source_root=root.as_posix();g.scan=first;g.second=second
        g.read_bytes=lambda a,n:lua.table_from(read(a,n))
        g.read_int=lambda a:struct.unpack('<i',read(a,4))[0]
        g.commands=lua.table_from(native_command_fixture(variant))
        g.allocate=lambda *args:writes.append(args)
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=second,readBytes=read_bytes,readInteger=read_int,allocate=allocate}
modules={protocol={getNativeCommandInterface=function() return commands end}}
phases=require('code/maintenance-native')
''')
        return lua
    lua=fixture();result=lua.globals().phases.verify()
    expected=lua.execute((root/'tests/fixtures/maintenance-sites.lua').read_text())[variant]
    assert result.gameState==expected.gameState
    for key in ('maintenance','world'):
        assert result[key].address==expected[key].address
        assert list(result[key].bytes.values())==list(expected[key].bytes.values())
    assert result.world.target==expected.world.target
    for _ in range(100):lua.globals().phases.verify()
    assert len(scans)==2 and not writes
    negative=0
    for pattern,address in list(matches.items()):
        saved=read(address,1);image[address-base]=0xcc
        for stale in (False,True):
            bad=fixture((lambda p:address if p==pattern else scan(p)) if stale else scan)
            bad.execute('assert(not pcall(phases.verify))');negative+=1
        image[address-base:address-base+1]=saved
        bad=fixture(second=lambda p,start:address+100 if p==pattern else scan(p,start))
        bad.execute('assert(not pcall(phases.verify))');negative+=1
    caller=result.guards[1].address
    for a in (caller+1,caller+11,caller+16,caller+21,result.maintenance.address+1,
              result.maintenance.address+11,result.maintenance.address+53,result.world.address+3):
        saved=read(a,4);image[a-base:a-base+4]=bytes(4)
        fixture().execute('assert(not pcall(phases.verify))');negative+=1
        image[a-base:a-base+4]=saved
    for guard in (result.guards[1],result.guards[2],result.maintenance.guard,result.world.guard):
        current=fixture();profile=current.globals().phases.verify()
        a=guard.address;saved=read(a,1);image[a-base]=0xcc
        current.globals().profile=profile
        current.execute('assert(not pcall(phases.new,{},profile,function() end))');negative+=1
        assert not writes
        image[a-base:a-base+1]=saved
    return dict(variant=variant,sha256=hashlib.sha256(raw).hexdigest(),bindings=4,
                negativeCases=negative,discoveryCalls=2,liveGame=False)
