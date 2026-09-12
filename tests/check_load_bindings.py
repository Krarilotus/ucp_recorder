"""Original images with actual UI/Protocol APIs; Map ABI metadata is a fixture."""
import hashlib
from pathlib import Path
import re
import struct
import pefile
from lupa.lua54 import LuaRuntime
from native_save_fixture import native_save_fixture


class LoadFixture:
    def __init__(self,path,variant,protocol,ui,framework):
        self.root=Path(__file__).resolve().parents[1]
        self.raw=path.read_bytes();pe=pefile.PE(data=self.raw)
        self.base=pe.OPTIONAL_HEADER.ImageBase
        self.image=bytearray(pe.get_memory_mapped_image());self.scans=[];self.matches={}
        self.variant=variant;self.protocol=protocol;self.ui=ui;self.framework=framework

    def read(self,a,n):
        assert self.base<=a and a+n<=self.base+len(self.image),hex(a)
        return bytes(self.image[a-self.base:a-self.base+n])

    def write(self,a,value):self.image[a-self.base:a-self.base+len(value)]=value

    def scan(self,pattern,start=None,stop=None):
        self.scans.append((pattern,start))
        regex=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=(start or self.base)-self.base
        found=re.search(regex,self.image[offset:(stop-self.base) if stop else None],re.DOTALL)
        address=self.base+offset+found.start() if found else 0
        if start is None:self.matches[pattern]=address
        return address

    def lua(self):
        lua=LuaRuntime(unpack_returned_tuples=True);g=lua.globals()
        g.root=self.root.as_posix();g.protocol_root=self.protocol.as_posix()
        g.ui_root=self.ui.as_posix();g.framework=self.framework.as_posix()
        g.scan=self.scan;g.read_bytes=lambda a,n:lua.table_from(self.read(a,n))
        g.read_int=lambda a:struct.unpack('<i',self.read(a,4))[0]
        g.save=lua.table_from(native_save_fixture(self.variant))
        lua.execute('''
package.path=root..'/?.lua;'..protocol_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,
 exposeCode=function() return function() end end}
package.loaded.core=core;log=function() end;utils=dofile(framework..'/utils.lua')
package.loaded['game.version']={setMultiplayerGameVersion=function() end}
package.loaded['game.hooks']={setHooks=function() end};hooks={registerHookCallback=function() end}
local owner=dofile(protocol_root..'/init.lua');owner:enable({})
local proxies=dofile(framework..'/extensions/proxies.lua')
modules={protocol=proxies.ExtensionProxy(owner),luajit={},
 ['map-extensions']={getNativeSaveInterface=function() return save end}}
package.loaded.manager={initialize=function() end};package.loaded.patches={}
local ui=dofile(ui_root..'/init.lua');modules.ui=proxies.ExtensionProxy(ui)
require('code/engine-state-sites').resolve()
resolver=require('code/load-sites')
''')
        return lua


def check(path,variant,protocol,ui,framework):
    fixture=LoadFixture(path,variant,protocol,ui,framework)
    lua=fixture.lua();before=len(fixture.scans);result=lua.globals().resolver.resolve()
    expected=lua.execute((fixture.root/'tests/fixtures/engine-sites.lua').read_text(encoding='utf-8'))[variant]
    for key,value in result.items():
        if not expected[key]:continue
        if isinstance(value,(int,float)):assert value==expected[key],key
        else:
            assert value.address==expected[key].address,key
            assert list(value.bytes.values())==list(expected[key].bytes.values()),key
    entries=(0x442877,0x4428c6,0x46b358,0x495337,0x494ba5) if variant=='SHC' else (
        0x442a37,0x442a86,0x46b578,0x495497,0x494d05)
    for key,address in zip(('beginMatch','prepareMatch','menuTransition','loadBegin','resetMatch'),entries):
        assert result[key].address==address
    patterns=[p for p,start in fixture.scans[before:] if start is None]
    for _ in range(100):lua.globals().resolver.resolve();lua.globals().resolver.verify()
    assert len(fixture.scans)-before==8
    negative=0
    for pattern in patterns:
        a=fixture.matches[pattern]
        for kind in ('missing','stale','ambiguous'):
            current=fixture.lua();g=current.globals();saved=fixture.read(a,1)
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start: a+100 if p==pattern else fixture.scan(p,start)
            else:
                fixture.write(a,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p: a if p==pattern else fixture.scan(p)
            current.execute('assert(not pcall(resolver.resolve))');negative+=1
            fixture.write(a,saved)
    for key,value in result.items():
        if isinstance(value,(int,float)):continue
        for late in (False,True):
            current=fixture.lua()
            if late:current.globals().resolver.resolve()
            a=value.guard.address;saved=fixture.read(a,1);fixture.write(a,b'\xcc')
            current.execute('assert(not pcall(resolver.verify))');negative+=1
            fixture.write(a,saved)
    a=result.load.address;b=result.loadBegin.address;r=result.resetMatch.guard.address
    for address in (a+21,a+39,a+50,a+60,a+45,b+2,b+8,b+39,r+54,r+15,r+25,r+20,
                    result.prepareMatch.guard.address+20,result.loadWorldComplete.guard.address+8):
        current=fixture.lua();saved=fixture.read(address,4);fixture.write(address,bytes(4))
        current.execute('assert(not pcall(resolver.resolve))');negative+=1
        fixture.write(address,saved)
    # Map wraps the first five reader bytes. Its retained internal filename call
    # and completion boundary must still resolve without rescanning the prologue.
    a=native_save_fixture(variant)['readWorld'];saved=fixture.read(a,5)
    fixture.write(a,b'\xe9\x01\x02\x03\x04');fixture.lua().globals().resolver.verify();fixture.write(a,saved)
    return dict(variant=variant,sha256=hashlib.sha256(fixture.raw).hexdigest(),bindings=11,
                negativeCases=negative,newDiscoveryCalls=8,mapWrapperCases=1,liveGame=False)
