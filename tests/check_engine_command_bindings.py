"""Actual Protocol/framework proxy and Recorder contexts on a private PE; no game."""
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
    scans=[];matches={}
    def read(a,n):
        assert base<=a and a+n<=base+len(image),hex(a)
        return bytes(image[a-base:a-base+n])
    def scan(pattern,start=None,stop=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:(stop-base) if stop else None],re.DOTALL)
        address=base+offset+found.start() if found else 0
        if start is None:matches[pattern]=address
        return address
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
package.loaded.core=core;log=function() end
utils=dofile(framework..'/utils.lua')
package.loaded['game.version']={setMultiplayerGameVersion=function() end}
package.loaded['game.hooks']={setHooks=function() end}
hooks={registerHookCallback=function() end}
local owner=dofile(protocol_root..'/init.lua');owner:enable({})
local proxies=dofile(framework..'/extensions/proxies.lua')
modules={protocol=proxies.ExtensionProxy(owner)}
resolver=require('code/engine-command-sites')
''')
        return lua
    lua=fixture();before=len(scans)
    result=lua.globals().resolver.resolve()
    expected=lua.execute((root/'tests/fixtures/engine-sites.lua').read_text(encoding='utf-8'))[variant]
    keys=('queue','select','copySize','localTimed','commandBoundary','execute','executed')
    for key in keys:
        assert result[key].address==expected[key].address,key
        assert list(result[key].bytes.values())==list(expected[key].bytes.values()),key
    for key in ('selectedOffset','selectedCountOffset','actorOffset'):assert result[key]==expected[key],key
    for _ in range(100):lua.globals().resolver.resolve();lua.globals().resolver.verify()
    assert len(scans)-before==2 # Only maintenance caller discovery; Protocol entries reused.
    negative=0
    for key in keys:
        guard=result[key].guard
        for late in (False,True):
            current=fixture()
            if late:current.globals().resolver.resolve()
            a=guard.address;saved=read(a,1);image[a-base]=0xcc
            current.execute('assert(not pcall(resolver.verify))');negative+=1
            image[a-base:a-base+1]=saved
    # Semantic operands are wildcarded for relocation but must agree with the owner.
    dispatcher=result.commandBoundary.address-48
    for a in (result.select.address+8,result.select.address+27,result.select.address+84,
              dispatcher+24,dispatcher+37,dispatcher+91,dispatcher+139,
              result.localTimed.guard.address+5,result.select.address+42):
        current=fixture();saved=read(a,4);image[a-base:a-base+4]=bytes(4)
        current.execute('assert(not pcall(resolver.resolve))');negative+=1
        image[a-base:a-base+4]=saved
    current=fixture();current.globals().resolver.resolve()
    a=result.copySize.ownerGuard.address;saved=read(a,1);image[a-base]=0xcc
    current.execute('assert(not pcall(resolver.verify))');negative+=1
    image[a-base:a-base+1]=saved
    # Protocol owns the adjacent seven-byte switch-table dispatch patch.
    # Recorder's full identifying context ends before that patch.
    a=dispatcher+151;saved=read(a,7);image[a-base:a-base+7]=b'\xe9\x01\x02\x03\x04\x90\x90'
    fixture().globals().resolver.verify()
    image[a-base:a-base+7]=saved
    return dict(variant=variant,sha256=hashlib.sha256(raw).hexdigest(),bindings=10,
                negativeCases=negative,consumerDiscoveryCalls=2,adjacentOwnerPatchCases=1,liveGame=False)
