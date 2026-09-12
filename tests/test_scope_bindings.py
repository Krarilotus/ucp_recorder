"""Relocated scope callers and disagreement with the existing subsystem owners."""
from pathlib import Path
import json
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=json.loads((ROOT/'tests/fixtures/scoped-operands.json').read_text(encoding='utf-8'))
SHIFT=0x10000000


class ScopeBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path;contexts=require('code/scoped-contexts');resolver=require('code/scoped-sites')")
        self.memory={};self.scans=[];self.patterns={};self.addresses={}
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for spec in g.contexts.values():
            reference=REFERENCE['contexts'][spec.name];a=reference['address']+SHIFT
            self.addresses[spec.name]=a;self.patterns[spec.pattern]=a
            for i,t in enumerate(spec.pattern.split()):self.memory[a+i]=0 if t=='?' else int(t,16)
            for offset,value,reloc in reference['fields']:word(a+offset,value+(SHIFT if reloc else 0))
        for key,value in REFERENCE['extra'].items():
            a=value['address']+SHIFT;self.addresses[key]=a
            for i,b in enumerate(value['bytes']):self.memory[a+i]=b
        controls=self.lua.table()
        for key,value in REFERENCE['controls'].items():
            site=self.lua.table_from({k:v for k,v in value.items() if k!='bytes'})
            site.address+=SHIFT
            if site.target is not None:site.target+=SHIFT
            site.bytes=self.lua.table_from(value['bytes'])
            site.guard=self.lua.table_from({'address':site.address,'bytes':site.bytes})
            controls[key]=site;self.addresses[key]=site.address
            for i,b in enumerate(value['bytes']):self.memory[site.address+i]=b
        def scan(pattern,start=None):
            self.scans.append((pattern,start));return 0 if start else self.patterns[pattern]
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.shift=SHIFT;g.controls=controls;g.seedAddress=self.addresses['seed']
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
package.loaded['code/engine-state-sites']={resolve=function() return {gameCore=shift+0x1fe7d10} end,
 controls=function() return controls end}
package.loaded['code/native-command']={bind=function() return {commands={handler=shift+0x191d768,
 localPlayer=shift+0x1a275dc,tick=shift+0x1fe7da8}} end}
package.loaded['code/rng-bindings']={resolve=function() return {state=shift+0x1a279c0,
 streams={{address=shift+0x46a800},{address=shift+0x46a7d0}}} end,
 seed=function() return require('code/hook-check').context(seedAddress,
 '56 6A 00 8B F1 E8 ? ? ? ? 83 C4 04 89 46 04 5E C3','seed') end}
''')

    def test_all_original_gates_relocate_and_discover_once(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local byName={};local result=resolver.verify(123)
for _,site in ipairs(result) do byName[site.name]=site end
for _,reference in ipairs(require('tests/fixtures/scoped-sites').SHC) do
 local site=assert(byName[reference.name]);assert(site.address==reference.address+shift)
 assert(site.kind==reference.kind and site.patch==reference.patch and site.condition==reference.condition)
 if reference.target then assert(site.target==reference.target+shift) end
end
for i=1,100 do assert(resolver.verify(123)==result) end
''')
                self.assertEqual(len(self.scans),32)

    def test_owner_disagreement_and_occupied_contexts_reject_before_install(self):
        for runtime in (Lua54,LuaJIT):
            self.prepare(runtime)
            fields=[]
            for spec in self.lua.globals().contexts.values():
                fields.extend((spec.name,f[1]) for f in spec.rngFields.values())
                fields.extend((spec.name,f[1]) for f in spec.ownerFields.values())
                fields.extend((spec.name,s.offset+1) for s in spec.sites.values() if s.stream)
            for name,offset in fields:
                with self.subTest(runtime=runtime,name=name,offset=offset):
                    self.prepare(runtime);self.word(self.addresses[name]+offset,0)
                    self.lua.execute('assert(not pcall(resolver.verify,123))')
            for key in self.addresses:
                for late in (False,True):
                    with self.subTest(runtime=runtime,key=key,late=late):
                        self.prepare(runtime)
                        if late:self.lua.globals().resolver.resolve(123)
                        self.memory[self.addresses[key]]=0xcc
                        self.lua.execute('assert(not pcall(resolver.verify,123))')
            for fail in ('AOBScan','scanForAOB'):
                self.prepare(runtime)
                self.lua.execute('core.'+fail+'=function() return '+('0' if fail=='AOBScan' else '1')+' end')
                self.lua.execute('assert(not pcall(resolver.verify,123))')
