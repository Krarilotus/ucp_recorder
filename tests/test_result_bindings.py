"""Relocated result contexts and owner agreement in both supported Lua runtimes."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class ResultBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path;patterns=require('code/result-patterns');resolver=require('code/result-sites')")
        self.addresses={'timer':0x11000000,'resources':0x12000000,'store':0x13000000,
                        'pack':0x14000000,'score':0x15000000}
        self.memory={};self.scans=[]
        for key,a in self.addresses.items():
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        def fields(key,values):
            for offset,value in values.items():word(self.addresses[key]+offset,value)
        fields('timer',{34:0x20000000,42:0x21000000,50:0x22000000,58:0x22002376,
                        70:0x16000000-0x1100004a})
        fields('resources',{21:0x2300003c,55:0x23000000})
        fields('store',{6:0x14000000-0x1300000a,17:181,22:0x24000bec,0x3a:0x240003ec,
                        0x3f:0x24000fdc,0x6c:0x24000bf0,0x9d:0x24000bf0,
                        0xa7:0x24000000,0xaf:0x24000bec,0xbc:0x24000bec})
        fields('pack',{5:0x24000000,24:0x24000004,37:0x20000000,
                       0x2b:0x15000000-0x1400002f,0x33:0x240003ec,0x42:0x2500032a,
                       0x61:0x240003f0,0x16c:0x22002314,0x17f:0x24000460,
                       0x18e:0x25000000,0x193:0x24000478})
        for source,dest,base,width,start in (
            ([0x56,0x5b,0x67,0x73,0x7d,0x89,0x95,0x9f],[0x6d,0x78,0x83,0x8f,0x9a,0xa5,0xb1,0xbc],0x26000000,4,0x3f4),
            ([0xab,0xb7,0xc1,0xcd,0xd9,0xe3,0xef,0xfb],[0xc7,0xd3,0xde,0xe9,0xf5,0x100,0x10d,0x11a],0x27000000,4,0x418),
            ([0x107,0x114,0x121,0x12d,0x13a,0x147,0x153,0x160],[0x126,0x133,0x140,0x14c,0x159,0x166,0x173,0x179],0x21000000,2,0x43c)):
            for i,(read,write) in enumerate(zip(source,dest),1):fields('pack',{read:base+width*i,write:0x24000000+start+4*i})
        fields('score',{8:0x25000334,22:0x250005bd,30:0x25000634,52:0x25000610,
                        71:0x25000714,77:0x2500070c,90:0x25000710,96:0x25000718})
        def scan(pattern,start=None):
            self.scans.append((pattern,start))
            return 0 if start else next(a for k,a in self.addresses.items() if pattern==g.patterns[k])
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
package.loaded['code/engine-state-sites']={resolve=function() return {gameCore=0x22000000} end}
package.loaded['code/native-command']={bind=function() return {commands={localPlayer=0x20000000}} end}
package.loaded['code/load-sites']={resolve=function() return {menuTransition={guard={address=0x16000000}}} end}
''')

    def test_relocated_native_state_and_cached_resolution(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local b=resolver.resolve();local s=b.statistics
assert(s.pack==0x14000000 and s.score==0x15000000 and s.temporary==0x24000000)
assert(s.results==0x25000000 and s.groups==0x26000000 and s.ai==0x27000000 and s.alive==0x21000000)
assert(b.records==0x24000bf0 and b.storedCount==0x24000bec and b.insertion.address==0x130000ad)
local input={keep=42};local e=resolver.bind(input)
assert(e.keep==42 and input.resultsTimer==nil and e.resultsTimer.address==0x1100001a)
assert(e.resultsTimer.kind=='raw' and e.resultsTimer.patch=='equalFlags')
assert(e.resultsBranch.address==0x1100001f and e.resourceReset.address==0x12000034 and e.playerResources==0x23000000)
for i=1,100 do assert(resolver.verify()==b) end
''')
                self.assertEqual(len(self.scans),6)

    def test_context_conflicts_and_operand_disagreement_fail_before_use(self):
        cases=[('timer',o) for o in (34,42,50,58,70)]+[('resources',o) for o in (21,55)]
        cases += [('store',o) for o in (6,17,22,0x3a,0x3f,0x6c,0x9d,0xa7,0xaf,0xbc)]
        cases += [('pack',o) for o in (5,24,37,0x2b,0x33,0x42,0x61,0x16c,0x17f,0x18e,0x193,0x56,0x67,0x6d,0x100,0x107,0x160,0x179)]
        cases += [('score',o) for o in (8,22,30,52,71,77,90,96)]
        for runtime in (Lua54,LuaJIT):
            for key,offset in cases:
                with self.subTest(runtime=runtime,key=key,offset=offset):
                    self.prepare(runtime);self.word(self.addresses[key]+offset,0)
                    self.lua.execute('assert(not pcall(resolver.verify))')
            for key in self.addresses:
                for late in (False,True):
                    with self.subTest(runtime=runtime,key=key,late=late):
                        self.prepare(runtime)
                        if late:self.lua.globals().resolver.resolve()
                        self.memory[self.addresses[key]]=0xcc
                        self.lua.execute('assert(not pcall(resolver.verify))')
            for failure in ('missing','ambiguous'):
                with self.subTest(runtime=runtime,failure=failure):
                    self.prepare(runtime)
                    self.lua.execute('core.'+('AOBScan' if failure=='missing' else 'scanForAOB')+'=function() return '+('0' if failure=='missing' else '0x18000000')+' end')
                    self.lua.execute('assert(not pcall(resolver.verify))')
