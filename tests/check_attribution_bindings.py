"""Verify diagnostic caller identity and original stacks on each native image."""
import hashlib
from check_load_bindings import LoadFixture
from check_spawn_context_native import check_spawn_context,check_fire_context


def check(path,variant,protocol,ui,framework):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua();g=lua.globals()
    lua.execute("require('code/rng-bindings').resolve()")
    before=len(f.scans)
    spawn=lua.eval("(require('code/rng-spawn-context'))");fire=lua.eval("(require('code/rng-fire-context'))")
    b=spawn.verify();calls=fire.verify()
    reference=lua.eval("(require('tests/fixtures/rng-spawn-context'))")[variant]
    assert b.entry==reference.entry and b.call==reference.call
    assert dict(calls.items())==dict(lua.eval("require('tests/fixtures/rng-fire-context').verify")(variant).items())
    for _ in range(100):spawn.verify();fire.verify()
    assert len(f.scans)-before==6
    patterns=[p for p,start in f.scans[before:] if start is None]
    def fresh(name):
        lua.execute("package.loaded['code/rng-"+name+"-context']=nil")
        return lua.eval("(require('code/rng-"+name+"-context'))")
    negative=0
    for pattern in patterns:
        address=f.matches[pattern];name='spawn' if address==b.entry else 'fire'
        for kind in ('missing','stale','ambiguous','late'):
            r=fresh(name);saved=f.read(address,1)
            if kind=='late':r.verify()
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start:address+100 if p==pattern else f.scan(p,start)
            else:
                f.write(address,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p:address if p==pattern else f.scan(p)
            ok,_=lua.eval('function(r) local ok,e=pcall(r.verify);return ok,e end')(r)
            assert not ok;negative+=1;f.write(address,saved);g.core.AOBScan=f.scan;g.core.scanForAOB=f.scan
    for name,address,offsets in [('spawn',b.entry,[25,44,60,89,95,375,386,391])]+[
          ('fire',a-20,[5,11,16,38,45,101 if kind=='ignite' else 109]) for a,kind in calls.items()]:
        for offset in offsets:
            saved=f.read(address+offset,4);f.write(address+offset,bytes(4));r=fresh(name)
            ok,_=lua.eval('function(r) local ok,e=pcall(r.verify);return ok,e end')(r)
            assert not ok,(name,offset);negative+=1;f.write(address+offset,saved)
    # Diagnostic resolution occurs after the existing observer patches both RNG
    # entries. It reuses their cached identity without scanning those prologues.
    for stream in lua.eval("require('code/rng-bindings').resolve().streams").values():
        saved=f.read(stream.address,6);f.write(stream.address,b'\xe9'+bytes(5))
        fresh('spawn').verify();fresh('fire').verify();f.write(stream.address,saved)
    check_spawn_context(f.read,lua,f.root,variant)
    check_fire_context(f.read,lua,f.root,variant)
    return dict(variant=variant,sha256=hashlib.sha256(f.raw).hexdigest(),callers=3,
                negativeCases=negative,newDiscoveryCalls=6,priorObserverHookCases=2,
                nativeSpawnStackCases=1,nativeFireStackCases=4,liveGame=False)
