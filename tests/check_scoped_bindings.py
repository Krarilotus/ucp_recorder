"""Actual owner APIs, complete caller inventory and original native selectors."""
import hashlib
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
import struct
from check_load_bindings import LoadFixture
from check_presentation_native import check_heads_placement
from check_taunt_native import check_taunts
from check_wedding_native import check_weddings
from test_scoped_code import ScopedCodeTests


def check(path,variant,protocol,ui,framework):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua();g=lua.globals()
    before=len(f.scans);resolver=lua.eval("(require('code/scoped-sites'))");sites=resolver.verify(123)
    expected=lua.eval("(require('tests/fixtures/scoped-sites'))")[variant]
    by_name={s.name:s for s in sites.values()}
    for reference in expected.values():
        actual=by_name[reference.name]
        for key in ('address','kind','patch','target','condition'):assert actual[key]==reference[key],(reference.name,key)
        assert list(actual.bytes.values())==list(reference.bytes.values()),reference.name
    patterns=[p for p,start in f.scans[before:] if start is None]
    for _ in range(100):resolver.verify(123)
    assert len(f.scans)-before==32
    def fresh():
        lua.execute("package.loaded['code/scoped-sites']=nil")
        return lua.eval("(require('code/scoped-sites'))")
    negative=0
    for pattern in patterns:
        a=f.matches[pattern]
        for kind in ('missing','stale','ambiguous'):
            saved=f.read(a,1);r=fresh()
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start: a+100 if p==pattern else f.scan(p,start)
            else:
                f.write(a,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p: a if p==pattern else f.scan(p)
            ok,_=lua.eval('function(r) local ok,e=pcall(r.verify,123);return ok,e end')(r)
            assert not ok;negative+=1;f.write(a,saved)
            g.core.AOBScan=f.scan;g.core.scanForAOB=f.scan
    for site in sites.values():
        for late in (False,True):
            r=fresh()
            if late:r.resolve(123)
            saved=f.read(site.address,1);f.write(site.address,b'\xcc')
            ok,_=lua.eval('function(r) local ok,e=pcall(r.verify,123);return ok,e end')(r)
            assert not ok;negative+=1;f.write(site.address,saved)
    # A changed optional seed hook cannot disable ordinary RNG/scope binding.
    seed=by_name['seed'];saved=f.read(seed.address,6);f.write(seed.address,b'\xe9'+bytes(5))
    r=fresh();assert len(r.verify())==27
    ok,_=lua.eval('function(r) local ok,e=pcall(r.verify,123);return ok,e end')(r);assert not ok
    f.write(seed.address,saved)
    # Compare the gate's passive execution with every original overwritten span.
    fixture=ScopedCodeTests();fixture.lua=lua
    fixture.emitter=lua.execute((f.root/'code/scoped-code.lua').read_text(encoding='utf-8'))
    cases=0
    for site in sites.values():
        for flags in (0x202,0xa83):
            original=fixture.run_code(site,0,0,flags,False)
            for enabled,mode in ((0,0),(0,99),(1,1),(1,2)):
                assert fixture.run_code(site,enabled,mode,flags,True)==original,(site.name,enabled,mode)
                cases+=1
    check_heads_placement(f.read,lua,variant,sites)
    check_taunts(path,lua,variant,sites)
    check_weddings(path,lua,variant,sites)
    # Whole native audio-function inventory, including all conditional branches.
    decoder=Cs(CS_ARCH_X86,CS_MODE_32);rng=lua.eval("require('code/rng-bindings').resolve().streams[1].address")
    functions=[(0x47a340,0x47a510,0x212,{f'moodMusic{i}' for i in range(1,8)}),
      (0x44bce0,0x44bf10,0x701,{'ambientSound'}),(0x471720,0x471940,0xcf,{'resourceSpeech'}),
      (0x47a130,0x47a300,0x80,{'audioLaunch'}),(0x47ab10,0x47ace0,0x424,{'battleMusic1','battleMusic2'}),
      (0x47b890,0x47ba60,0x68d,{'ambientMusic'})]
    for shc,extreme,size,names in functions:
        start=shc if variant=='SHC' else extreme
        ins=list(decoder.disasm(f.read(start,size),start))
        assert ins[-1].address+ins[-1].size==start+size
        calls={i.address for i in ins if i.bytes[0]==0xe8 and len(i.bytes)==5
          and i.address+5+struct.unpack('<i',i.bytes[1:])[0]==rng}
        assert calls=={by_name[name].address for name in names},names
    return dict(variant=variant,sha256=hashlib.sha256(f.raw).hexdigest(),bindings=28,
                negativeCases=negative,newDiscoveryCalls=32,optionalSeedCases=2,
                nativePassiveGateCases=cases,completeAudioCallerInventory=True,
                nativeHeadsTauntWeddingChecks=True,liveGame=False)
