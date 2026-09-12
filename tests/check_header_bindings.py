"""Private-image header capture with actual writer instructions; no game."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import pefile
from lupa.lua54 import LuaRuntime
from test_world_header import PARTS


def check(path,variant):
    root=Path(__file__).resolve().parents[1]
    raw=path.read_bytes(); pe=pefile.PE(data=raw)
    base=pe.OPTIONAL_HEADER.ImageBase
    image=bytearray(pe.get_memory_mapped_image())
    matches={}; data_reads=[]; scans=[]
    def scan(pattern,start=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=max(0,(start or base)-base)
        found=re.search(expression,image[offset:],re.DOTALL)
        address=base+offset+found.start() if found else 0
        if start is None: matches[pattern]=address
        return address
    def read(a,n):
        assert base<=a and a+n<=base+len(image),hex(a)
        return bytes(image[a-base:a-base+n])
    def fixture(aob=scan,second=scan):
        lua=LuaRuntime(unpack_returned_tuples=True,encoding='latin-1')
        g=lua.globals(); g.source_root=root.as_posix()
        g.scan,g.second=aob,second
        g.read_bytes=lambda a,n:lua.table_from(read(a,n))
        g.read_int=lambda a:struct.unpack('<I',read(a,4))[0]
        def data(a,n): data_reads.append((a,n)); return read(a,n)
        g.read_data=data
        g.hash_data=lambda d:hashlib.sha256(d.encode('latin-1')).hexdigest()
        lua.execute("""
package.path=source_root..'/?.lua;'..package.path
core={AOBScan=scan,scanForAOB=second,readBytes=read_bytes,readInteger=read_int,readString=read_data}
sha={sha256=hash_data}; header=require('code/world-header')
""")
        return lua
    lua=fixture(); captured,descriptor=lua.globals().header.read()
    expected=[(p[1] if variant=='SHC' else p[2],p[0]) for _,parts in PARTS for p in parts]
    assert data_reads==expected
    assert captured.encode('latin-1')==b''.join(read(a,n) for a,n in expected)
    lua.globals().header.validate(captured,descriptor)
    for _ in range(10): lua.globals().header.read()
    assert len(scans)==10 and len(matches)==5
    negative=0
    for pattern,address in list(matches.items()):
        saved=image[address-base]; image[address-base]=0xcc
        for stale in (False,True):
            lua=fixture((lambda p:address if p==pattern else scan(p)) if stale else scan)
            data_reads.clear()
            lua.execute('assert(not pcall(header.read))')
            assert not data_reads; negative+=1
        image[address-base]=saved
        lua=fixture(second=lambda p,start:address+0x1000 if p==pattern else scan(p,start))
        data_reads.clear(); lua.execute('assert(not pcall(header.read))')
        assert not data_reads; negative+=1
    for _,parts in PARTS:
        for _,_,_,reference in parts:
            operand=reference+(0 if variant=='SHC' else 0x230)+1
            saved=read(operand,4)
            image[operand-base:operand-base+4]=bytes(4)
            lua=fixture(); data_reads.clear(); lua.execute('assert(not pcall(header.read))')
            assert not data_reads; negative+=1
            image[operand-base:operand-base+4]=saved
    return dict(variant=variant,referenceSha256=hashlib.sha256(raw).hexdigest(),
                bindings=18,negativeCases=negative,bytes=2141,liveGame=False)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--variant',choices=['SHC','Extreme'],required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=check(a.reference,a.variant)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
