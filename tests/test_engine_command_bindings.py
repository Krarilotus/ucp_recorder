"""Relocated owner entries, operand agreement and pre-install conflict checks."""
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class EngineCommandBindingTests(unittest.TestCase):
    def prepare(self,runtime):
        self.lua=runtime(unpack_returned_tuples=True)
        g=self.lua.globals();g.root=ROOT.as_posix()
        self.lua.execute('''
package.path=root..'/?.lua;'..package.path
resolver=require('code/engine-command-sites')
for i=1,20 do local k,v=debug.getupvalue(resolver.resolve,i)
 if k=='patterns' then patterns=v end
end
assert(patterns)
''')
        self.memory={}
        for a,n in ((0x10000000,69),(0x11000000,79)):
            for i in range(n):self.memory[a+i]=0x90
        for a,key in ((0x11000143,'copy'),(0x100000fc,'localTimed'),(0x12000000,'dispatcher'),
                      (0x120000a0,'executed'),(0x13000000,'selector')):
            for i,t in enumerate(g.patterns[key].split()):self.memory[a+i]=0 if t=='?' else int(t,16)
        def word(a,v):
            for i,b in enumerate(struct.pack('<I',v&0xffffffff)):self.memory[a+i]=b
        self.word=word
        for a,v in ((0x10000006,0x109ee0),(0x10000101,0x109ee4),
                    (0x12000004,0x13000000-0x12000008),(0x12000018,0x10a20c),
                    (0x12000025,0x109eec),(0x1200005b,0x109e70),(0x1200008b,0x109ee4),
                    (0x13000008,0x109eec),(0x1300001b,0x10a20c),(0x1300002a,0x109edc),
                    (0x13000054,0x31000000)):word(a,v)
        g.read_bytes=lambda a,n:self.lua.table_from(self.memory[a+i] for i in range(n))
        g.read_int=lambda a:struct.unpack('<i',bytes(self.memory[a+i] for i in range(4)))[0]
        self.lua.execute('''
core={readBytes=read_bytes,readInteger=read_int,
 AOBScan=function() error('Must reuse owner entries') end,
 scanForAOB=function() error('Must reuse owner entries') end}
local function bytes(a,n) return string.char((table.unpack or unpack)(core.readBytes(a,n))) end
commands={version=1,handler=0x20000000,ring=0x2003c67c,stride=1272,capacity=200,
 writeIndex=0x20109ee0,currentCommand=0x2002d824,localPlayer=0x20109e74,
 tick=0x31000000,receivedParameters=0x20000cdc,scheduleCommand=function() end,
 queueEntry=0x10000000,scheduleEntry=0x11000000,
 queueBytes=bytes(0x10000000,69),scheduleBytes=bytes(0x11000000,79)}
modules={protocol={getNativeCommandInterface=function() return commands end}}
package.loaded['code/maintenance-sites']={resolve=function() return {commandDispatcher=0x12000000} end}
''')

    def test_relocated_bindings_reuse_entries_and_decode_layout_once(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                self.prepare(runtime)
                self.lua.execute('''
local input={preserved=42};local sites=resolver.bind(input)
assert(input.queue==nil and sites.preserved==42)
assert(sites.queue.address==0x10000000 and #sites.queue.bytes==10)
assert(sites.select.address==0x13000000 and #sites.select.bytes==5)
assert(sites.copySize.address==0x11000165 and sites.localTimed.address==0x10000116)
assert(sites.commandBoundary.address==0x12000030 and sites.execute.address==0x1200008f)
assert(sites.executed.address==0x120000a0 and sites.selectedOffset==0x109eec)
assert(sites.selectedCountOffset==0x10a20c and sites.actorOffset==0x109e70)
local binding=resolver.resolve()
for i=1,100 do assert(resolver.resolve()==binding);resolver.verify() end
''')

    def test_invalid_owner_layout_and_changed_guards_reject_before_install(self):
        for runtime in (Lua54,LuaJIT):
            for case in ('owner','queue','schedule','dispatch','selector','copy','timed','executed',
                         'count','actor','tick','index','lateQueue','lateSchedule','lateDispatch'):
                with self.subTest(runtime=runtime,case=case):
                    self.prepare(runtime)
                    if case.startswith('late'):self.lua.globals().resolver.resolve()
                    addresses={'queue':0x10000000,'schedule':0x11000000,'dispatch':0x12000000,
                               'selector':0x13000000,'copy':0x11000143,'timed':0x100000fc,
                               'executed':0x120000a0,'lateQueue':0x10000020,
                               'lateSchedule':0x11000020,'lateDispatch':0x12000020}
                    if case=='owner':self.lua.execute("commands.queueBytes='' ")
                    elif case in addresses:self.memory[addresses[case]]=0xcc
                    else:self.word({'count':0x1300001b,'actor':0x1200005b,
                                    'tick':0x13000054,'index':0x1200008b}[case],0)
                    self.lua.execute('assert(not pcall(resolver.verify))')
