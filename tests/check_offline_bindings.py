"""Native offline boundaries, prior owner hooks and original/patched gates."""
import hashlib
from check_load_bindings import LoadFixture
from check_save_pacing_native import check_save_pacing
from test_scoped_code import ScopedCodeTests


def check(path,variant,protocol,ui,framework):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua()
    before=len(f.scans);resolver=lua.eval("(require('code/offline-sites'))");b=resolver.verify()
    expected=lua.eval("(require('tests/fixtures/offline-sites'))")[variant]
    for key,value in expected.items():
        for field in ('address','patch','value','pop'):assert b[key][field]==value[field],(key,field)
        assert list(b[key].bytes.values())==list(value.bytes.values()),key
    patterns=[p for p,start in f.scans[before:] if start is None]
    for _ in range(100):resolver.verify()
    assert len(f.scans)-before==8
    negative=0
    for pattern in patterns:
        a=f.matches[pattern]
        for kind in ('missing','stale','ambiguous'):
            current=f.lua();g=current.globals();saved=f.read(a,1)
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start: a+100 if p==pattern else f.scan(p,start)
            else:
                f.write(a,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p: a if p==pattern else f.scan(p)
            current.execute("assert(not pcall(require('code/offline-sites').verify))")
            negative+=1;f.write(a,saved)
    commands=lua.eval("require('code/native-command').bind({}).commands")
    worker=b.syncPolling.address+50+lua.globals().core.readInteger(b.syncPolling.address+46)
    contexts=[site.guard.address for site in b.values()]+[commands.queueEntry+0x11c,worker]
    for a in contexts:
        for late in (False,True):
            current=f.lua();r=current.eval("(require('code/offline-sites'))")
            if late:r.resolve()
            saved=f.read(a,1);f.write(a,b'\xcc')
            current.execute("assert(not pcall(require('code/offline-sites').verify))")
            negative+=1;f.write(a,saved)
    # Phase resolution captures the native receive CALL before Recorder replaces
    # the preceding returned-tick MOV. Queue context starts after the timed hook.
    current=f.lua();phase=current.eval("require('code/maintenance-sites').resolve()")
    changed=[(phase.guards[1].address+20,5),(commands.queueEntry+0x116,6)]
    saved=[(a,f.read(a,n)) for a,n in changed]
    for a,n in changed:f.write(a,b'\xe9'+bytes(n-1))
    current.execute("require('code/offline-sites').verify()")
    for a,raw in saved:f.write(a,raw)
    # Use the production bindings with the existing emitter preservation check.
    fixture=ScopedCodeTests();fixture.lua=lua
    fixture.emitter=lua.execute((f.root/'code/scoped-code.lua').read_text(encoding='utf-8'))
    cases=0
    for name,site in b.items():
        for flags in (0x202,0xa83):
            original=fixture.run_code(site,0,2,flags,False)
            assert fixture.run_code(site,0,2,flags,True,local_gate=True)==original,(name,'passive')
            active=fixture.run_code(site,1,2,flags,True,local_gate=True)
            assert active[1:7]==(0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000)
            assert active[8]==flags
            if site.patch=='return':assert active[7]==0x4108004+(site.pop or 0) and active[-3]==0x4f1000
            else:assert active[0]==99 and active[7]==0x4108000
            cases+=3
    check_save_pacing(f.read,lua,f.root,variant,b.savePacing)
    return dict(variant=variant,sha256=hashlib.sha256(f.raw).hexdigest(),bindings=10,
                negativeCases=negative,newDiscoveryCalls=8,priorRecorderHooks=2,
                nativeGateCases=cases,nativeSavePacingCases=64,liveGame=False)
