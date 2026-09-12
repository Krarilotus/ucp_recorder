"""Actual owner APIs, native history operands and original packer/date writes."""
import hashlib
from check_load_bindings import LoadFixture
from check_battle_history_native import check as check_native


def check(path,variant,protocol,ui,framework):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua()
    result=lua.eval("require('code/result-sites').resolve()")
    before=len(f.scans);resolver=lua.eval("(require('code/history-sites'))");b=resolver.verify()
    expected=lua.eval("(require('tests/fixtures/history-sites'))")[variant]
    for key,value in expected.items():
        if isinstance(value,(int,float)):assert b[key]==value,key
        elif key=='operands':
            for i,v in value.items():
                for field in ('address','offset','kind','delta'):assert b.operands[i][field]==v[field],(i,field)
                assert list(b.operands[i].bytes.values())==list(v.bytes.values())
        else:assert b[key].address==value.address and list(b[key].bytes.values())==list(value.bytes.values()),key
    patterns=[p for p,start in f.scans[before:] if start is None]
    for _ in range(100):resolver.verify()
    assert len(f.scans)-before==4
    negative=0
    for pattern in patterns:
        a=f.matches[pattern]
        for kind in ('missing','stale','ambiguous'):
            current=f.lua();g=current.globals();saved=f.read(a,1)
            if kind=='ambiguous':g.core.scanForAOB=lambda p,start: a+100 if p==pattern else f.scan(p,start)
            else:
                f.write(a,b'\xcc')
                if kind=='stale':g.core.AOBScan=lambda p: a if p==pattern else f.scan(p)
            current.execute("assert(not pcall(require('code/history-sites').verify))")
            negative+=1;f.write(a,saved)
    sorter=b.prepareList.address+5+lua.globals().core.readInteger(b.prepareList.address+1)
    contexts=(b.prepareList.guard.address,b.action.guard.address,b.frame.guard.address,
              b.operands[1].guard.address,b.helpText.guard.address,sorter)
    for a in contexts:
        for late in (False,True):
            current=f.lua();r=current.eval("(require('code/history-sites'))")
            if late:r.resolve()
            saved=f.read(a,1);f.write(a,b'\xcc')
            current.execute("assert(not pcall(require('code/history-sites').verify))")
            negative+=1;f.write(a,saved)
    for operand in b.operands.values():
        a=operand.address+operand.offset;saved=f.read(a,4);current=f.lua();f.write(a,bytes(4))
        current.execute("assert(not pcall(require('code/history-sites').verify))")
        negative+=1;f.write(a,saved)
    check_native(path.parent,b,result.statistics.pack,variant)
    return dict(variant=variant,sha256=hashlib.sha256(f.raw).hexdigest(),bindings=22,
                negativeCases=negative,newDiscoveryCalls=4,completeNativeDataOperandInventory=True,
                nativePackerDateWritesConfined=True,liveGame=False)
