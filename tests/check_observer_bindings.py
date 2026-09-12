"""Network/hash observer bindings on private PE images; no live process."""
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
    matches={};scans=[];hooks=[]
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
        g.commandFixture=lua.table_from(native_command_fixture(variant))
        g.hook=lambda callback,a,n:hooks.append((a,n))
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=second,readBytes=read_bytes,readInteger=read_int,detourCode=hook}
modules={protocol={getNativeCommandInterface=function() return commandFixture end}}
network=require('code/network-observer');world=require('code/world-hash-observer')
function verify() return network.verify(),world.verify() end
''')
        return lua
    lua=fixture();network,world=lua.globals().verify()
    expected=lua.execute((root/'tests/fixtures/network-sites.lua').read_text())[variant]
    expected_world=lua.execute((root/'tests/fixtures/world-hash-sites.lua').read_text())[variant]
    for name,site in network.items():
        assert site.address==expected[name].address and list(site.bytes.values())==list(expected[name].bytes.values())
    assert world.address==expected_world.address and list(world.bytes.values())==list(expected_world.bytes.values())
    for _ in range(100):lua.globals().verify()
    assert len(scans)==8 and not hooks
    # Protocol's already-installed seven-byte dispatch patches are outside
    # Recorder's discovery/guard spans. Mimic those occupied adjacent sites.
    for site in (network.remoteImmediate,network.localImmediate):
        a=site.address+len(site.bytes);saved=read(a,7)
        image[a-base:a-base+7]=b'\xe9'+bytes(4)+b'\x90\x90'
        fixture().globals().verify()
        image[a-base:a-base+7]=saved
    negative=0
    for pattern,address in list(matches.items()):
        saved=read(address,1);image[address-base]=0xcc
        for stale in (False,True):
            bad=fixture((lambda p:address if p==pattern else scan(p)) if stale else scan)
            bad.execute('assert(not pcall(verify))');negative+=1
        image[address-base:address-base+1]=saved
        bad=fixture(second=lambda p,start:address+100 if p==pattern else scan(p,start))
        bad.execute('assert(not pcall(verify))');negative+=1
    for guard,offsets in ((network.remoteImmediate.guard,(2,50)),
                          (network.localImmediate.guard,(20,68)),(world.guard,(2,25,69))):
        for offset in offsets:
            a=guard.address+offset;saved=read(a,4);image[a-base:a-base+4]=bytes(4)
            fixture().execute('assert(not pcall(verify))');negative+=1
            image[a-base:a-base+4]=saved
    for site,owner in [(s,'network') for _,s in network.items()]+[(world,'world')]:
        current=fixture();current.globals().verify()
        a=site.address;saved=read(a,1);image[a-base]=0xcc
        current.execute(f'assert(not pcall({owner}.install,{{}}))');negative+=1
        assert not hooks
        image[a-base:a-base+1]=saved
    return dict(variant=variant,referenceSha256=hashlib.sha256(raw).hexdigest(),bindings=4,
                negativeCases=negative,discoveryCalls=8,adjacentProtocolPatches=2,liveGame=False)
