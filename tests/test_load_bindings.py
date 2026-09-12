"""Relocated lifecycle owners, internal native calls and strict load guards."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class LoadBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute('''
package.path=root..'/?.lua;'..package.path
resolver=require('code/load-sites')
for i=1,20 do local k,v=debug.getupvalue(resolver.resolve,i)
 if k=='patterns' then patterns=v end
end
assert(patterns)
''')
        self.memory={};self.scans=[]
        for a,n in ((0x14000000,61),(0x19000000,60)):
            for i in range(n):self.memory[a+i]=0x90
        addresses={'prepare':0x1400003d,'load':0x15000000,'begin':0x15000287,'done':0x15000724,
                   'reset':0x16000000,'readFile':0x13000044,'fileName':0x18000000,
                   'mapName':0x17000000,'readComplete':0x13000700}
        for key,a in addresses.items():
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for a,v in ((0x14000051,0x21002384),(0x15000015,0x20000618),
                    (0x15000027,0x20000cbc),(0x15000032,0x22000058),
                    (0x15000289,0x2200007c),(0x1500028f,0x22000080),(0x150002ae,0x2100000c),
                    (0x16000036,0x23000000),(0x15000725,0x23000000),
                    (0x1600003b,0x24000000-0x1600003f),(0x1500072a,0x24000000-0x1500072e),
                    (0x1600000f,0x21000000),(0x16000019,0x22000000),
                    (0x16000014,0x19000000-0x16000018),
                    (0x13000047,0x25000000),(0x1300004c,0x18000000-0x13000050),
                    (0x13000708,0x21002370),(0x1300070e,0x2100236c)):word(a,v)
        def scan(pattern,start=None):
            self.scans.append((pattern,start))
            key=next(k for k in ('load','reset','mapName','readComplete') if g.patterns[k]==pattern)
            return 0 if start else addresses[key]
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
package.loaded['code/engine-state-sites']={resolve=function() return {gameCore=0x21000000,menuText=0x22000000} end}
local rng={initialization={address=0x14000000,bytes=core.readBytes(0x14000000,61)}}
package.loaded['code/rng-bindings']={resolve=function() return rng end}
local commands={version=1,handler=0x20000000,ring=0x2003c67c,stride=1272,capacity=200,
 writeIndex=0x20109ee0,currentCommand=0x2002d824,localPlayer=0x20109e74,
 tick=0x21000098,receivedParameters=0x20000cdc,scheduleCommand=function() end}
menu={version=1,entry=0x19000000,gameCore=0x21000000,
 bytes=string.char((table.unpack or unpack)(core.readBytes(0x19000000,60)))}
modules={protocol={getNativeCommandInterface=function() return commands end},
 ui={getNativeMenuInterface=function() return menu end},
 ['map-extensions']={getNativeSaveInterface=function() return {version=1,sectionCount=122,
 descriptorSize=16,readWorld=0x13000000,writeWorld=0x26000000,sections=0x27000000,packager=0x28000000} end}}
''')

    def test_resolves_all_hooks_through_relocated_owners_without_repeated_scans(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local input={preserved=42};local b=resolver.bind(input)
assert(input.load==nil and b.preserved==42)
assert(b.beginMatch.address==0x14000000 and b.prepareMatch.address==0x1400004f)
assert(b.menuTransition.address==0x19000018 and b.load.address==0x15000000)
assert(b.loadBegin.address==0x15000287 and b.loadHandlerComplete.address==0x15000724)
assert(b.resetMatch.address==0x16000035 and b.loadWorldComplete.address==0x13000712)
assert(b.mapName.address==0x17000000 and b.fileName.address==0x18000000 and b.resources==0x25000000)
local cached=resolver.resolve();for i=1,100 do assert(resolver.resolve()==cached);resolver.verify() end
''')
                self.assertEqual(len(self.scans),8)

    def test_missing_ambiguous_owner_mismatch_and_changed_guard_reject(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','ambiguous','ui','uiState','prepare','handler','selection','reset',
                         'menuCall','filename','readComplete','lateRead','lateInit','lateMenu','lateDone'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case.startswith('late'):self.lua.globals().resolver.resolve()
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='ambiguous':self.lua.execute('core.scanForAOB=function() return 1 end')
                    elif case=='ui':self.lua.execute("menu.bytes='' ")
                    elif case=='uiState':self.lua.execute('menu.gameCore=0')
                    else:
                        a={'prepare':0x14000051,'handler':0x15000015,'selection':0x150002ae,
                           'reset':0x16000036,'menuCall':0x16000014,'filename':0x18000004,
                           'readComplete':0x1300070e,'lateRead':0x13000710,'lateInit':0x14000003,
                           'lateMenu':0x1900000a,'lateDone':0x1500072e}[case]
                        self.memory[a]^=0xff
                    self.lua.execute('assert(not pcall(resolver.verify))')
