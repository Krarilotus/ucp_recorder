"""Relocated observer contexts, owner agreement, and all-or-nothing hook guards."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class ObserverBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True)
        g=self.lua.globals();g.source_root=ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
ns=require('code/network-sites');ws=require('code/world-hash-sites')
for i=1,20 do local k,v=debug.getupvalue(ns.resolve,i);if k=='contexts' then contexts=v end end
for i=1,20 do local k,v=debug.getupvalue(ws.resolve,i);if k=='pattern' then worldPattern=v end end
assert(contexts and worldPattern)
''')
        self.memory={};self.patterns={};self.scans=[];self.hooks=[]
        for i,key in enumerate(('systemMessage','remoteImmediate','localImmediate','world')):
            address=0x10000000+i*0x1000
            pattern=g.worldPattern if key=='world' else g.contexts[key].pattern
            self.patterns[pattern]=address
            for j,t in enumerate(pattern.split()):self.memory[address+j]=0 if t=='?' else int(t,16)
        def put(a,v):
            for i,b in enumerate(struct.pack('<I',v)):self.memory[a+i]=b
        self.put=put
        for a,v in [(0x10001002,0x109e70),(0x10001032,0x109ee4),
                    (0x10002014,0x109e74),(0x10002044,0x109e70),
                    (0x10003002,0x109e74),(0x10003019,0x109e74),(0x10003045,0x30000000)]:put(a,v)
        def scan(pattern,start=None):
            self.scans.append((pattern,start));return 0 if start else self.patterns[pattern]
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.hook=lambda callback,a,n:self.hooks.append((a,n))
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int,detourCode=hook}
modules={protocol={getNativeCommandInterface=function()
 return {handler=0x30000000,localPlayer=0x30109e74,writeIndex=0x30109ee0}
end}}
network=require('code/network-observer');world=require('code/world-hash-observer')
function verify() return network.verify(),world.verify() end
''')

    def test_relocated_sites_preserve_spans_and_do_not_rescan(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local sites,hash=verify()
assert(sites.systemMessage.address==0x10000000 and #sites.systemMessage.bytes==5)
assert(sites.remoteImmediate.address==0x10001036 and #sites.remoteImmediate.bytes==7)
assert(sites.localImmediate.address==0x10002048 and #sites.localImmediate.bytes==8)
assert(hash.address==0x10003024 and #hash.bytes==11)
for i=1,100 do verify() end
network.install({});world.install({})
''')
                self.assertEqual(len(self.scans),8)
                self.assertEqual(set(self.hooks),{(0x10000000,5),(0x10001036,7),(0x10002048,8),(0x10003024,11)})

    def test_discovery_owner_and_late_conflicts_prevent_hooking(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('missing','duplicate','modified','owner','late_network','late_world'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    action='verify'
                    if case=='missing':self.lua.execute('core.AOBScan=function() return 0 end')
                    elif case=='duplicate':self.lua.execute('core.scanForAOB=function() return 1 end')
                    elif case=='modified':self.memory[0x1000204e]=0xcc
                    elif case=='owner':self.put(0x10001002,0x109e80)
                    else:
                        self.lua.execute('verify()')
                        self.memory[0x10002000 if case=='late_network' else 0x10003000]=0xcc
                        action='network.install' if case=='late_network' else 'world.install'
                    self.lua.execute(f'assert(not pcall({action},{{}}))')
                    self.assertFalse(self.hooks)
