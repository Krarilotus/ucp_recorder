"""Resolve the actual codec against a private executable; no game is launched."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import pefile
from lupa.lua54 import LuaRuntime


def check(path, variant):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes()
    pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase
    image=bytearray(pe.get_memory_mapped_image())
    expected={'SHC':(0x4724c0,0x4725a0),'Extreme':(0x4726e0,0x4727c0)}[variant]
    matches={}
    def scan(pattern,start=None):
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:],re.DOTALL)
        address=base+offset+found.start() if found else 0
        if start is None: matches[pattern]=address
        return address
    def fixture(aob=scan, second=scan):
        lua=LuaRuntime(unpack_returned_tuples=True)
        g=lua.globals()
        g.source_root=root.as_posix()
        g.scan,g.second=aob,second
        g.read=lambda a,n:lua.table_from(image[a-base:a-base+n])
        g.expected=lua.table_from(expected)
        lua.execute("""
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/binary-memory']={prepare=function() end}
exposed=0
core={AOBScan=scan,scanForAOB=second,readBytes=read,exposeCode=function(a,n,abi)
 assert((a==expected[1] or a==expected[2]) and n==6 and abi==1)
 exposed=exposed+1; return function() end
end}
codec=require('code/world-codec')
""")
        return lua
    lua=fixture()
    assert lua.globals().codec.compressorAddress()==expected[0]
    assert lua.globals().exposed==2 and len(matches)==2
    negative=0
    for pattern,address in list(matches.items()):
        for offset in (0,35):
            original=image[address-base+offset]
            image[address-base+offset]=0xcc
            for stale_cache in (False,True):
                # A cached match must also be verified, before exposing calls.
                lua=fixture((lambda p:address if p==pattern else scan(p)) if stale_cache else scan)
                lua.execute('assert(not pcall(codec.compressorAddress)); assert(exposed==0)')
                negative+=1
            image[address-base+offset]=original
        lua=fixture(second=lambda p,start:address+0x1000 if p==pattern else scan(p,start))
        lua.execute('assert(not pcall(codec.compressorAddress)); assert(exposed==0)')
        negative+=1
    return dict(variant=variant,referenceSha256=hashlib.sha256(raw).hexdigest(),
                bindings=2,negativeCases=negative,liveGame=False)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--variant',choices=['SHC','Extreme'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=check(a.reference,a.variant)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
