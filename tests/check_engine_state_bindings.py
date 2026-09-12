"""Native coordinator/calendar bindings through actual Protocol and framework."""
import hashlib
from pathlib import Path
import re
import struct
import pefile
from lupa.lua54 import LuaRuntime


def check(path,variant,protocol,framework):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes();pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase;image=bytearray(pe.get_memory_mapped_image())
    scans=[]
    def read(a,n):
        assert base<=a and a+n<=base+len(image),hex(a)
        return bytes(image[a-base:a-base+n])
    def scan(pattern,start=None,stop=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:(stop-base) if stop else None],re.DOTALL)
        return base+offset+found.start() if found else 0
    def fixture():
        lua=LuaRuntime(unpack_returned_tuples=True)
        g=lua.globals();g.root=root.as_posix();g.protocol_root=protocol.as_posix()
        g.framework=framework.as_posix();g.scan=scan
        g.read_bytes=lambda a,n:lua.table_from(read(a,n))
        g.read_int=lambda a:struct.unpack('<i',read(a,4))[0]
        lua.execute('''
package.path=root..'/?.lua;'..protocol_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,
 exposeCode=function() return function() end end}
package.loaded.core=core;log=function() end;utils=dofile(framework..'/utils.lua')
package.loaded['game.version']={setMultiplayerGameVersion=function() end}
package.loaded['game.hooks']={setHooks=function() end}
hooks={registerHookCallback=function() end}
local owner=dofile(protocol_root..'/init.lua');owner:enable({})
local proxies=dofile(framework..'/extensions/proxies.lua')
modules={protocol=proxies.ExtensionProxy(owner)}
require('code/maintenance-sites').resolve();require('code/rng-bindings').resolve()
resolver=require('code/engine-state-sites')
''')
        return lua
    lua=fixture();before=len(scans);result=lua.globals().resolver.resolve()
    expected=lua.execute((root/'tests/fixtures/engine-sites.lua').read_text(encoding='utf-8'))[variant]
    for key,value in result.items():
        if isinstance(value,(int,float)):assert value==expected[key],key
        else:
            assert value.address==expected[key].address,key
            assert list(value.bytes.values())==list(expected[key].bytes.values()),key
    assert result.calendar.value==expected.calendar.value
    for _ in range(100):lua.globals().resolver.resolve();lua.globals().resolver.verify()
    assert len(scans)-before==2 # Calendar only; all other entries reuse owners.
    negative=0
    tick=result.tickEntry.address;c=result.tick.guard.address;p=tick+0x1e8
    navigation=result.navigationCountdown
    # Obtain the navigation callee from the already verified maintenance call.
    phase=lua.eval("require('code/maintenance-sites').resolve()")
    call=phase.maintenance.address+47;nav=call+5+struct.unpack('<i',read(call+1,4))[0]
    guards=[result.tickEntry.guard,result.tickExit.guard,result.tick.guard,
            result.tickReturned.guard,result.haltingMenu.guard,result.calendar.guard]
    for guard in guards:
        for late in (False,True):
            current=fixture()
            if late:current.globals().resolver.resolve()
            a=guard.address;saved=read(a,1);image[a-base]=0xcc
            current.execute('assert(not pcall(resolver.verify))');negative+=1
            image[a-base:a-base+1]=saved
    for a in (tick+2,c+1,c+16,c+47,c+68,c+74,p+10,p+18,p+25,p+38,p+46,
              result.haltingMenu.address+1,nav+40,nav+58,result.calendar.guard.address+47,
              result.calendar.guard.address+8):
        current=fixture();saved=read(a,4);image[a-base:a-base+4]=bytes(4)
        current.execute('assert(not pcall(resolver.resolve))');negative+=1
        image[a-base:a-base+4]=saved
    # Both full non-hook contexts must also be guarded against late changes.
    for a in (nav,p):
        current=fixture();current.globals().resolver.resolve()
        saved=read(a,1);image[a-base]=0xcc
        current.execute('assert(not pcall(resolver.verify))');negative+=1
        image[a-base:a-base+1]=saved
    calendar_pattern=next(pattern for pattern,start in scans if pattern.startswith('8B 54 24 08 33 C0'))
    for kind in ('missing','stale','duplicate'):
        current=fixture();g=current.globals()
        a=result.calendar.guard.address;saved=read(a,1)
        if kind=='duplicate':g.core.scanForAOB=lambda pattern,start: a+100 if pattern==calendar_pattern else scan(pattern,start)
        else:
            image[a-base]=0xcc
            if kind=='stale':g.core.AOBScan=lambda pattern: a if pattern==calendar_pattern else scan(pattern)
        current.execute('assert(not pcall(resolver.resolve))');negative+=1
        image[a-base:a-base+1]=saved
    a=nav+62;saved=read(a,4);image[a-base:a-base+4]=struct.pack('<I',50)
    current=fixture();assert current.globals().resolver.resolve().navigationCountdown==navigation
    current.globals().resolver.verify();image[a-base:a-base+4]=saved
    return dict(variant=variant,sha256=hashlib.sha256(raw).hexdigest(),bindings=10,
                negativeCases=negative,newDiscoveryCalls=2,legacyPeriodCases=1,liveGame=False)
