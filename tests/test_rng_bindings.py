"""Relocated RNG binding, initialization-only scans and pre-hook rejection."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class RNGBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True)
        g=self.lua.globals();g.source_root=ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
rng=require('code/rng-bindings')
for i=1,20 do local k,v=debug.getupvalue(rng.resolve,i);if k=='patterns' then patterns=v end end
assert(patterns)
''')
        self.memory={};self.sites={};self.scans=[];self.hooks=[]
        for i,key in enumerate(('initialization','stream1','stream2')):
            address=0x10000000+i*0x1000;self.sites[key]=address
            for j,t in enumerate(g.patterns[key].split()):self.memory[address+j]=0 if t=='?' else int(t,16)
        seed=bytes.fromhex('56 6A 00 8B F1 E8 00 00 00 00 83 C4 04 89 46 04 5E C3')
        for i,b in enumerate(seed):self.memory[0x10003000+i]=b
        def put(a,v):
            for i,b in enumerate(struct.pack('<I',v)):self.memory[a+i]=b
        put(0x10000001,0x30000000);put(0x10000006,0x2ff6)
        put(0x10000019,0x31000000);put(0x1000002b,0x31000000)
        self.put=put
        self.patterns={g.patterns[k]:a for k,a in self.sites.items()}
        def scan(pattern,start=None):
            self.scans.append((pattern,start));return 0 if start else self.patterns[pattern]
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.hook=lambda callback,a,n:self.hooks.append((a,n))
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,detourCode=hook}
modules={protocol={getNativeCommandInterface=function() return {handler=0x31000000} end}}
''')

    def test_relocation_cached_use_and_original_instruction_hooks(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local value=rng.resolve()
assert(value.state==0x30000000 and value.streams[1].address==0x10001000 and value.streams[2].address==0x10002000)
for i=1,100 do assert(rng.resolve()==value) end
require('code/rng-observer').install({engine={rng=value.state}})
''')
                self.assertEqual(len(self.scans),6)
                self.assertEqual(self.hooks,[(0x10001000,6),(0x10002000,6)])

    def test_failure_before_binding_or_any_hook(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','duplicate','modified','state','seed','owner','occupied_after_resolve'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='duplicate':self.lua.execute('core.scanForAOB=function() return 42 end')
                    elif case=='modified':self.memory[0x10002020]=0xcc
                    elif case=='state':self.put(0x10000001,0)
                    elif case=='seed':self.memory[0x1000300d]=0xcc
                    elif case=='owner':self.put(0x1000002b,0x32000000)
                    elif case=='occupied_after_resolve':
                        self.lua.execute('rng.resolve()');self.memory[0x10002020]=0xcc
                    self.lua.execute("assert(not pcall(require('code/rng-observer').install,{engine={rng=0x30000000}}))")
                    self.assertFalse(self.hooks)
