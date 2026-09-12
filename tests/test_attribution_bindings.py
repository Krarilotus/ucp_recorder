"""Optional diagnostic bindings relocate and reject owner/context disagreement."""
from pathlib import Path
import json
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=json.loads((ROOT/'tests/fixtures/attribution-operands.json').read_text(encoding='utf-8'))
SHIFT=0x10000000


class AttributionBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path;patterns=require('code/attribution-patterns');spawn=require('code/rng-spawn-context');fire=require('code/rng-fire-context')")
        self.memory={};self.scans=[];self.patterns={};self.addresses={}
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for key,reference in REFERENCE.items():
            a=reference['address']+SHIFT;self.addresses[key]=a;self.patterns[g.patterns[key]]=a
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
            for offset,value,reloc in reference['fields']:word(a+offset,value+(SHIFT if reloc else 0))
        def scan(pattern,start=None):
            self.scans.append((pattern,start));return 0 if start else self.patterns[pattern]
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.shift=SHIFT
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
package.loaded['code/native-command']={bind=function() return {commands={tick=shift+0x1fe7da8}} end}
package.loaded['code/rng-bindings']={resolve=function() return {state=shift+0x1a279c0,
 streams={{address=shift+0x46a800},{address=shift+0x46a7d0}}} end}
''')

    def test_both_native_capacities_and_cached_relocated_callers(self):
        for runtime in (Lua54,LuaJIT):
            for capacity in (2500,10000):
                with self.subTest(runtime=runtime,capacity=capacity):
                    self.prepare(runtime);a=self.addresses['spawn']
                    self.word(a+25,capacity-1);self.word(a+44,capacity)
                    self.lua.execute('''
local b=spawn.verify();local f=fire.verify()
assert(b.entry==shift+0x53e440 and b.call==shift+0x53e5c6)
assert(f[shift+0x4052f4]=='ignite' and f[shift+0x4054f4]=='spread')
for i=1,100 do assert(spawn.verify()==b and fire.verify()==f) end
''')
                    self.assertEqual(len(self.scans),6)

    def test_missing_ambiguous_changed_and_wrong_owner_contexts(self):
        for runtime in (Lua54,LuaJIT):
            for key,offsets in [('spawn',[25,44,60,89,95,375,386,391]),
                                 ('ignite',[5,11,16,38,45,101]),('spread',[5,11,16,38,45,109])]:
                name='spawn' if key=='spawn' else 'fire'
                for offset in offsets:
                    with self.subTest(runtime=runtime,key=key,offset=offset):
                        self.prepare(runtime);self.word(self.addresses[key]+offset,0)
                        self.lua.execute('assert(not pcall('+name+'.verify))')
                for late in (False,True):
                    self.prepare(runtime)
                    if late:self.lua.globals()[name].verify()
                    self.memory[self.addresses[key]]=0xcc
                    self.lua.execute('assert(not pcall('+name+'.verify))')
                for fail in ('AOBScan','scanForAOB'):
                    self.prepare(runtime)
                    self.lua.execute('core.'+fail+'=function() return '+('0' if fail=='AOBScan' else '1')+' end')
                    self.lua.execute('assert(not pcall('+name+'.verify))')
