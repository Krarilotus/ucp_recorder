"""Relocated state owners and semantic/late-context failures on both runtimes."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class EngineStateBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True)
        g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute('''
package.path=root..'/?.lua;'..package.path
resolver=require('code/engine-state-sites')
for i=1,20 do local k,v=debug.getupvalue(resolver.resolve,i)
 if k=='patterns' then patterns=v end
end
assert(patterns)
''')
        self.memory={};self.scans=[]
        for a,n in ((0x11000000,64),(0x1000016c,80)):
            for i in range(n):self.memory[a+i]=0x90
        for a,key in ((0x10000000,'entry'),(0x1000007d,'exit'),(0x10000106,'clock'),
                      (0x100001e8,'pause'),(0x12000000,'menu'),(0x13000000,'navigation'),(0x14000000,'calendar')):
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for a,v in ((0x11000010,0x10000000-0x11000014),
                    (0x10000002,0x21000cbc),(0x1000000c,0x33000000),(0x10000018,0x21000790),
                    (0x10000020,0x21000000),(0x10000085,0x21000000),(0x1000008b,0x21000b98),
                    (0x10000094,0x15000000-0x10000098),(0x10000107,0x22000000),
                    (0x10000116,0x22002344),(0x10000127,0x22000000),
                    (0x1000012c,0x12000000-0x10000130),(0x10000135,0x23000000),
                    (0x1000013a,0x25000000-0x1000013e),(0x1000013f,0x23000000),
                    (0x10000144,0x24000000-0x10000148),(0x1000014a,0x22000098),
                    (0x10000150,0x30000000),(0x1000019c,0x13000000-0x100001a0),
                    (0x100001ea,0x33000000),(0x100001f2,0x22002344),
                    (0x100001fa,0x10000098-0x100001fe),(0x10000201,0x22000000),
                    (0x10000206,0x12000000-0x1000020a),(0x1000020e,0x10000098-0x10000212),
                    (0x10000216,0x22002344),(0x12000001,0x21000618),(0x12000013,0x3200005c),
                    (0x1300001f,0x30051a20),(0x13000028,0x30051a20),(0x1300003a,0x30051a20),
                    (0x1300003e,200),(0x14000024,0x519fc),(0x1400002f,0x51a00),
                    (0x1400001a,0x519f8),(0x14000008,0x51a14),(0x1400000e,0x51a0c),
                    (0x14000014,0x51a10)):word(a,v)
        def scan(pattern,start=None):
            self.scans.append((pattern,start));self.assertEqual(pattern,g.patterns.calendar)
            return 0 if start else 0x14000000
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
local phases={gameState=0x30000000,maintenance={address=0x1000016c},
 guards={{address=0x11000000,bytes=core.readBytes(0x11000000,64)}}}
package.loaded['code/maintenance-sites']={resolve=function() return phases end}
package.loaded['code/rng-bindings']={resolve=function() return {state=0x23000000,
 streams={{address=0x24000000},{address=0x25000000}}} end}
modules={protocol={getNativeCommandInterface=function() return {version=1,
 handler=0x21000000,ring=0x2103c67c,stride=1272,capacity=200,
 currentCommand=0x2102d824,writeIndex=0x21109ee0,localPlayer=0x21109e74,
 receivedParameters=0x21000cdc,tick=0x22000098,queueEntry=0x15000000,
 scheduleCommand=function() end} end}}
''')

    def test_relocated_native_state_and_legacy_period_without_repeat_discovery(self):
        for runtime in (Lua54,LuaJIT):
            for period in (50,200):
                with self.subTest(runtime=runtime,period=period):
                    self.prepare(runtime);self.word(0x1300003e,period)
                    self.lua.execute('''
local original={preserved=42};local b=resolver.bind(original)
assert(original.tick==nil and b.preserved==42)
assert(b.tickEntry.address==0x10000000 and b.tickExit.address==0x10000098)
assert(b.tick.address==0x10000134 and b.tickReturned.address==0x11000014)
assert(b.gameCore==0x22000000 and b.paused==0x22002344 and b.haltingMenu.address==0x12000000)
assert(b.calendar.address==0x1400001e and b.calendar.value==0x300519fc)
assert(b.menuText==0x32000000 and b.navigationCountdown==0x30051a20)
local cached=resolver.resolve();for i=1,100 do assert(resolver.resolve()==cached);resolver.verify() end
''')
                    self.assertEqual(len(self.scans),2)

    def test_missing_ambiguous_changed_and_inconsistent_bindings_reject(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','ambiguous','calendar','rng','clock','pause','queue','menu','countdown',
                         'lateCalendar','latePause','lateCountdown'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case.startswith('late'):self.lua.globals().resolver.resolve()
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='ambiguous':self.lua.execute('core.scanForAOB=function() return 123 end')
                    else:
                        address={'calendar':0x14000008,'rng':0x10000135,'clock':0x1000014a,
                                 'pause':0x10000216,'queue':0x10000094,'menu':0x12000001,
                                 'countdown':0x1300003a,'lateCalendar':0x14000004,
                                 'latePause':0x100001f6,'lateCountdown':0x13000014}[case]
                        self.memory[address]^=0xff
                    self.lua.execute('assert(not pcall(resolver.verify))')
