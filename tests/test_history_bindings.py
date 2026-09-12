"""Relocated history views, owner agreement and pre-install conflict checks."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class HistoryBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True);g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path;patterns=require('code/history-patterns');resolver=require('code/history-sites')")
        self.addresses={'prepare':0x11000000,'action':0x11000030,'frame':0x12000000,
                        'rows':0x120001d5,'help':0x120008a3,'sort':0x13000000}
        self.memory={};self.scans=[]
        for key,a in self.addresses.items():
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        def fields(key,values):
            for offset,value in values.items():word(self.addresses[key]+offset,value)
        fields('prepare',{1:0x13000000-0x11000005,13:0x21002380,38:0x20000618,43:0x22000000})
        fields('action',{12:0x23000000,38:0x24000000,0x63:0x25000000,0x224:0x26000000,
                         0x8a:0x21000068,0x94:0x20000618,0x82:0x27000000,
                         0x24d:0x13000000-(0x11000030+0x251),0x29e:0x13000000-(0x11000030+0x2a2),
                         0x22b:0x26000000,0x1f9:0x22000000,0x20c:0x22000000,
                         0x1fe:0x20000618,0x211:0x20000618,0x195:0x21000000,0x19b:0x21002377,
                         0x1eb:0x21000000,0x1a1:0x14000000-(0x11000030+0x1a5),
                         0x1f4:0x14000000-(0x11000030+0x1f8),0x207:0x14000000-(0x11000030+0x20b),
                         0x6f:0x28000440,0x78:0x28000478,0xa4:0x28000460,0x133:0x28000460,0x1c1:0x25000000})
        fields('action',{o:0x23000000 for o in (25,47,59,77,0x1ae,0x25f,0x266,0x2b0,0x2b7)})
        fields('action',{o:0x24000000 for o in (0x56,0x1b8,0x252,0x2a3)})
        fields('sort',{4:0x27fffffc,0x2f:0x28000000,0x59:0x28000000,0x79:0x26000000,
                       0x92:0x24000000,0xae:0x25000000,0xc0:0x24000000})
        fields('rows',{2:0x23000000,11:0x25000000,23:0x28000000})
        fields('help',{56:0x23000000,69:0x25000000,81:0x28000000})
        def scan(pattern,start=None):
            self.scans.append((pattern,start))
            return 0 if start else next(a for k,a in self.addresses.items() if pattern==g.patterns[k])
        g.scan=scan;g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        self.lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
package.loaded['code/engine-state-sites']={resolve=function() return {gameCore=0x21000000} end}
package.loaded['code/native-command']={bind=function() return {commands={handler=0x20000000}} end}
package.loaded['code/load-sites']={resolve=function() return {menuTransition={guard={address=0x14000000}}} end}
package.loaded['code/result-sites']={resolve=function()
 return {records=0x28000000,storedCount=0x27fffffc,statistics={results=0x27000000}} end}
''')

    def test_resolves_all_data_sources_and_reuses_native_result_owner(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local b=resolver.verify()
assert(b.records==0x28000000 and b.storedCount==0x27fffffc and b.savedMode==0x22000000)
assert(b.scroll==0x23000000 and b.count==0x24000000 and b.index==0x25000000 and b.sort==0x26000000)
assert(b.prepareList.address==0x11000000 and b.prepare.address==0x11000005)
assert(b.action.address==0x11000030 and b.frame.address==0x12000000 and b.helpText.address==0x120008d5)
assert(#b.operands==10)
for i=1,100 do assert(resolver.verify()==b) end
''')
                self.assertEqual(len(self.scans),4)

    def test_missing_ambiguous_modified_views_and_disagreeing_fields_fail(self):
        cases=[('prepare',o) for o in (1,13,38)]+[('action',o) for o in (12,38,0x63,0x224,0x82,0x8a,0x94,0x1f9,0x20c,0x195,0x19b,0x1a1,0x24d,0x29e,0x133)]
        cases += [('sort',o) for o in (4,0x2f,0x59,0x79,0x92,0xae,0xc0)]
        cases += [('rows',o) for o in (2,11,23)]+[('help',o) for o in (56,69,81)]
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
                    self.lua.execute('assert(not pcall(resolver.verify))')
