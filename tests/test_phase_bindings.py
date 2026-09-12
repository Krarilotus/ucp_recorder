"""Relocated coordinator call, decoded phases, and strict pre-install guards."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class PhaseBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True)
        g=self.lua.globals();g.source_root=ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
resolver=require('code/maintenance-sites')
for i=1,20 do local k,v=debug.getupvalue(resolver.resolve,i)
 if k=='patterns' then patterns=v elseif k=='worldPattern' then worldPattern=v end
end
assert(patterns and worldPattern)
phases=require('code/maintenance-native')
''')
        self.memory={};self.scans=[];self.writes=[]
        for address,pattern in [(0x10000000,g.patterns.caller),
                                (0x1001016c,g.patterns.maintenance),(0x10010234,g.patterns.world),
                                (0x10020000,g.worldPattern)]:
            for i,t in enumerate(pattern.split()):self.memory[address+i]=0 if t=='?' else int(t,16)
        def put(a,v):
            for i,b in enumerate(struct.pack('<I',v)):self.memory[a+i]=b
        self.put=put
        for a,v in [(0x10000001,0x30000000),(0x10000015,0x30000000),
                    (0x1000000b,0x31000000),(0x10000010,0x10000-20),(0x1000001a,0x30000-30),
                    (0x10010249,0x10020000-(0x10010234+25))]:put(a,v)
        for offset in (1,11,21,53,63):put(0x1001016c+offset,0x32000000)
        def scan(pattern,start=None):
            self.scans.append((pattern,start));self.assertEqual(pattern,g.patterns.caller)
            return 0 if start else 0x10000000
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.allocate=lambda *args:self.writes.append(args)
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,allocate=allocate}
modules={protocol={getNativeCommandInterface=function() return {handler=0x30000000} end}}
''')

    def test_resolves_phases_inside_relocated_coordinator_once(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
profile=phases.verify()
assert(profile.gameState==0x31000000 and profile.maintenance.address==0x1001016c)
assert(profile.world.address==0x10010246 and profile.world.target==0x10020000)
assert(profile.receiveEntry==0x10030000)
assert(#profile.maintenance.bytes==5 and #profile.world.bytes==7)
for i=1,100 do assert(phases.verify()==profile) end
''')
                self.assertEqual(len(self.scans),2);self.assertFalse(self.writes)

    def test_invalid_contexts_operands_and_late_conflicts_cannot_install(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','duplicate','owner','state','tile','callee','late'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='duplicate':self.lua.execute('core.scanForAOB=function() return 1 end')
                    elif case=='owner':self.put(0x10000015,0x30000004)
                    elif case=='state':self.put(0x1000000b,0)
                    elif case=='tile':self.put(0x1001016c+53,0x33000000)
                    elif case=='callee':self.memory[0x10020030]=0xcc
                    else:
                        self.lua.execute('profile=phases.verify()');self.memory[0x1001016c+30]=0xcc
                        self.lua.execute('assert(not pcall(phases.new,{},profile,function() end))')
                        self.assertFalse(self.writes);continue
                    self.lua.execute('assert(not pcall(phases.verify))');self.assertFalse(self.writes)
