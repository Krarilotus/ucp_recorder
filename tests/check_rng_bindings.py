"""Production RNG discovery on a private executable image; no game or hooks."""
import hashlib
from pathlib import Path
import re
import struct
import pefile
from lupa.lua54 import LuaRuntime
from native_command_fixture import native_command_fixture


def check(path,variant):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes(); pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase; image=bytearray(pe.get_memory_mapped_image())
    matches={}; scans=[]
    def read(a,n):
        assert base<=a and a+n<=base+len(image),hex(a)
        return bytes(image[a-base:a-base+n])
    def scan(pattern,start=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:],re.DOTALL)
        address=base+offset+found.start() if found else 0
        if start is None: matches[pattern]=address
        return address
    def fixture(first=scan,second=scan):
        lua=LuaRuntime(unpack_returned_tuples=True)
        g=lua.globals();g.source_root=root.as_posix();g.scan=first;g.second=second
        g.read_bytes=lambda a,n:lua.table_from(read(a,n))
        g.read_int=lambda a:struct.unpack('<i',read(a,4))[0]
        g.handler=native_command_fixture(variant)['handler']
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=second,readBytes=read_bytes,readInteger=read_int}
modules={protocol={getNativeCommandInterface=function() return {handler=handler} end}}
rng=require('code/rng-bindings')
''')
        return lua
    lua=fixture();result=lua.globals().rng.resolve()
    state=0x1a279c0 if variant=='SHC' else 0x24baec0
    entries=(0x46a800,0x46a7d0) if variant=='SHC' else (0x46aa20,0x46a9f0)
    assert result.state==state
    for i,expected in enumerate(entries,1):
        assert result.streams[i].address==expected
        assert bytes(result.streams[i].bytes.values())==read(expected,41 if i==1 else 42)
    for _ in range(100):lua.globals().rng.resolve()
    assert len(scans)==6
    negative=0
    for pattern,address in list(matches.items()):
        saved=read(address,1);image[address-base]=0xcc
        for stale in (False,True):
            bad=fixture((lambda p:address if p==pattern else scan(p)) if stale else scan)
            bad.execute('assert(not pcall(rng.resolve))');negative+=1
        image[address-base:address-base+1]=saved
        bad=fixture(second=lambda p,start:address+100 if p==pattern else scan(p,start))
        bad.execute('assert(not pcall(rng.resolve))');negative+=1
    initialization=next(a for p,a in matches.items() if p.startswith('B9 '))
    for offset in (1,6,25,43):
        saved=read(initialization+offset,4)
        image[initialization+offset-base:initialization+offset-base+4]=bytes(4)
        bad=fixture();bad.execute('assert(not pcall(rng.resolve))');negative+=1
        image[initialization+offset-base:initialization+offset-base+4]=saved
    return dict(variant=variant,referenceSha256=hashlib.sha256(raw).hexdigest(),
                bindings=3,negativeCases=negative,discoveryCalls=6,liveGame=False)
