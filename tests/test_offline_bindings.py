"""Relocated transport graph and owner relationships, without an executable."""
from pathlib import Path
import json
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]
REFERENCE=json.loads((ROOT/'tests/fixtures/offline-operands.json').read_text(encoding='utf-8'))
SHIFT=0x10000000


class OfflineBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path;patterns=require('code/offline-patterns');resolver=require('code/offline-sites')")
        self.memory={};self.scans=[]
        self.addresses={key:value['address']+SHIFT for key,value in REFERENCE['contexts'].items()}
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for key,value in REFERENCE['contexts'].items():
            a=self.addresses[key]
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
            for offset,field in value['fields']:word(a+offset,field+(SHIFT if 0x400000<=field<0x4000000 else 0))
        menu=REFERENCE['menu'];self.addresses['menu']=menu['address']+SHIFT
        for i,b in enumerate(menu['bytes']):self.memory[self.addresses['menu']+i]=b
        # The complete menu leaf has three absolute state reads.
        for offset in (1,19,38):
            v=struct.unpack('<I',bytes(menu['bytes'][offset:offset+4]))[0]
            word(self.addresses['menu']+offset,v+SHIFT)
        def scan(pattern,start=None):
            self.scans.append((pattern,start))
            return 0 if start else next(a for k,a in self.addresses.items() if k!='menu' and pattern==g.patterns[k])
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        g.shift=SHIFT
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
local menu={address=shift+0x46bd20,bytes=core.readBytes(shift+0x46bd20,45)}
package.loaded['code/engine-state-sites']={resolve=function() return {gameCore=shift+0x1fe7d10,haltingMenu={guard=menu}} end}
package.loaded['code/native-command']={bind=function() return {commands={handler=shift+0x191d768,
 queueEntry=shift+0x489100,writeIndex=shift+0x1a27648,tick=shift+0x1fe7da8}} end}
package.loaded['code/maintenance-sites']={resolve=function() return {receiveEntry=shift+0x490690} end}
package.loaded['code/native-save']={interface=function() return {writeWorld=shift+0x474480} end}
''')

    def test_relocated_native_graph_is_cached_and_install_is_idempotent(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local b=resolver.verify();local reference=require('tests/fixtures/offline-sites').SHC
for key,value in pairs(b) do
 assert(value.address==reference[key].address+shift and value.patch==reference[key].patch)
 assert(value.pop==reference[key].pop and value.value==reference[key].value)
end
for i=1,100 do assert(resolver.verify()==b) end
local installs=0
package.loaded['code/fixes']={install=function(sites,flag)
 assert(#sites==10 and flag==123);installs=installs+1 end}
local engine={offlineFlag=123};local runtime=require('code/offline-runtime')
runtime.install(engine);runtime.install(engine);assert(installs==1 and engine.offlineInstalled)
''')
                self.assertEqual(len(self.scans),8)

    def test_disagreeing_owner_fields_and_changed_contexts_cannot_install(self):
        cases=[('save',8),('save',37),('queue',13),('queue',78),('queue',19),('queue',26),('queue',42),
               ('worker',14),('worker',29),('worker',42),('worker',60),('worker',34),('worker',65),
               ('pacing',5),('pacing',22),('pacing',33),('pacing',84),('pacing',90),('receive',34),
               ('syncPolling',1),('syncPolling',27),('syncPolling',38),('syncPolling',46),
               ('autosave',41),('autosave',54),('autosave',66),('autosave',71),('lag',47),('lag',83),
               ('syncMessage',47),('syncPacket',49),('syncPacket',74)]
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
                    self.lua.execute('core.'+('AOBScan' if failure=='missing' else 'scanForAOB')+'=function() return '+('0' if failure=='missing' else '1')+' end')
                    self.lua.execute('''
package.loaded['code/fixes']={install=function() error('MUTATED') end}
local e={};local ok,reason=pcall(require('code/offline-runtime').install,e)
assert(not ok and not tostring(reason):find('MUTATED',1,true) and not e.offlineInstalled)
''')
