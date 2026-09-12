"""Actual Protocol/UI APIs and original result routines in private PE images."""
import hashlib
import struct
import time
from check_load_bindings import LoadFixture
from check_results_native import check_results
from check_match_results_native import check as check_insert
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EDI,UC_X86_REG_EDX
from native_image import load_image


def check_packer(path,fixture,binding):
    """Original cdecl packer/scorer, with only the OS local-date call stubbed."""
    m=Uc(UC_ARCH_X86,UC_MODE_32);load_image(m,path)
    m.mem_map(0x5000000,0x10000);stack,stop=0x5009000,0x5001000
    s=binding.statistics
    def put(a,v):m.mem_write(a,struct.pack('<I',v&0xffffffff))
    def call(a,arg):
        m.mem_write(stack,struct.pack('<II',stop,arg));m.reg_write(UC_X86_REG_ESP,stack)
        m.emu_start(a,stop,count=100000)
        assert m.reg_read(UC_X86_REG_ESP)==stack+4
        return m.reg_read(UC_X86_REG_EAX)
    p=s.pack
    name=struct.unpack('<I',fixture.read(p+18,4))[0]
    player=struct.unpack('<I',fixture.read(p+37,4))[0]
    lord=struct.unpack('<I',fixture.read(p+0x16c,4))[0]
    date=p+0x188+struct.unpack('<i',fixture.read(p+0x184,4))[0]
    m.mem_write(date,b'\xc3')
    for slot in range(9):
        put(player,slot);put(lord,4)
        m.mem_write(name,b'Binding fixture\0')
        raw=bytearray((i*17+slot)%256 for i in range(0x778))
        for i in range(9):
            raw[0x32a+i]=int(i<5)
            struct.pack_into('<I',raw,0x334+i*4,1000+i*10)
            raw[0x5bd+i]=i%4
            struct.pack_into('<I',raw,0x610+i*4,150+i*2)
            struct.pack_into('<I',raw,0x634+i*4,3+i)
        for offset,value in ((0x70c,1189),(0x710,3),(0x714,1190),(0x718,9)):
            struct.pack_into('<I',raw,offset,value)
        m.mem_write(s.results,bytes(raw))
        for i in range(9):
            put(s.groups+i*4,i%4);put(s.ai+i*4,16-i)
            m.mem_write(s.alive+i*2,struct.pack('<h',(-1,0,1)[i%3]))
        m.mem_write(s.temporary,b'\xa5'*0xbf0)
        score=(100+slot+100*(3+slot)+150+slot*2)
        expected=(score+(slot%4)*score//4)*200//218
        assert call(s.score,slot)==expected
        assert call(p,123)==1
        packed=bytes(m.mem_read(s.temporary,0xbf0))
        assert struct.unpack_from('<I',packed,0)[0]==123
        assert packed[4:20]==b'Binding fixture\0'
        assert struct.unpack_from('<I',packed,0x3ec)[0]==expected
        assert packed[0x478:]==bytes(raw)
        for i in range(1,9):
            assert struct.unpack_from('<I',packed,0x3f4+i*4)[0]==i%4
            assert struct.unpack_from('<I',packed,0x418+i*4)[0]==16-i
            assert struct.unpack_from('<i',packed,0x43c+i*4)[0]==(-1,0,1)[i%3]
        # Native reads accumulated arrays; only the temporary record may change.
        assert bytes(m.mem_read(s.results,0x778))==bytes(raw)
    return 18


def check_resources(fixture,binding):
    m=Uc(UC_ARCH_X86,UC_MODE_32);m.mem_map(0x400000,0x4000000)
    site=binding.engine.resourceReset;start=site.guard.address+35;end=site.guard.address+67
    m.mem_write(start,fixture.read(start,end-start))
    resources=binding.engine.playerResources
    for player in range(9):
        values=list(range(100,125));address=resources+player*0x39f4
        m.mem_write(address-4,struct.pack('<27I',777,*values,888))
        m.reg_write(UC_X86_REG_EDI,player);m.reg_write(UC_X86_REG_EDX,0);m.reg_write(UC_X86_REG_EAX,0)
        m.emu_start(start,end,count=1000)
        expected=[0]*25;expected[15]=values[15]
        assert struct.unpack('<27I',m.mem_read(address-4,108))==(777,*expected,888)
    return 9


def check(path,variant,protocol,ui,framework):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua()
    lua.globals().resolver.resolve() # prepare existing lifecycle owners first
    before=len(f.scans);start=time.perf_counter()
    resolver=lua.eval("(require('code/result-sites'))");b=resolver.verify()
    resolve_ms=(time.perf_counter()-start)*1000
    expected=lua.eval("(require('tests/fixtures/result-sites'))")[variant]
    for key,value in expected.statistics.items():assert b.statistics[key]==value,key
    assert b.insertion.address==expected.insertion.address and b.insertion.records==expected.insertion.records
    engine_expected=lua.eval("(require('tests/fixtures/engine-sites'))")[variant]
    for key,value in b.engine.items():
        if isinstance(value,(int,float)):assert value==engine_expected[key],key
        else:assert value.address==engine_expected[key].address and list(value.bytes.values())==list(engine_expected[key].bytes.values()),key
    patterns=[p for p,start in f.scans[before:] if start is None]
    for _ in range(100):resolver.verify()
    assert len(f.scans)-before==6
    negative=0
    for pattern in patterns:
        a=f.matches[pattern]
        for kind in ('missing','stale','ambiguous'):
            current=f.lua();g=current.globals();saved=f.read(a,1)
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start: a+100 if p==pattern else f.scan(p,start)
            else:
                f.write(a,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p: a if p==pattern else f.scan(p)
            current.execute("assert(not pcall(require('code/result-sites').verify))")
            negative+=1;f.write(a,saved)
    contexts=(b.engine.resultsTimer.guard.address,b.engine.resourceReset.guard.address,
              b.insertion.guard.address,b.statistics.pack,b.statistics.score)
    for a in contexts:
        for late in (False,True):
            current=f.lua();r=current.eval("(require('code/result-sites'))")
            if late:r.resolve()
            saved=f.read(a,1);f.write(a,b'\xcc')
            current.execute("assert(not pcall(require('code/result-sites').verify))")
            negative+=1;f.write(a,saved)
    # The production contexts feed the existing original/patched timer harness.
    combined=resolver.bind(lua.eval("require('code/engine-state-sites').bind({})"))
    check_results(f.read,lua,f.root,variant,combined)
    check_insert(path.parent,b,variant)
    pack_cases=check_packer(path,f,b)
    resource_cases=check_resources(f,b)
    return dict(variant=variant,sha256=hashlib.sha256(f.raw).hexdigest(),bindings=14,
                negativeCases=negative,newDiscoveryCalls=6,privateImageResolutionMs=round(resolve_ms,3),
                resultsTimerCases=192,insertionCases=4,packerScoreCases=pack_cases,
                resourceRecountCases=resource_cases,liveGame=False)
