"""Actual Protocol public API to Recorder; the native call bridge is a stand-in."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT
import test_recorder as fixture


class NativeCommandOwnerTests(unittest.TestCase):
    def test_owner_callable_and_relocated_metadata_reach_the_engine(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime),patch.object(fixture,'LuaRuntime',runtime):
                fixture.RecorderTests.setUp(self)
                self.lua.globals().protocol_root=Path(os.environ.get('UCP_PROTOCOL_TEST_ROOT',
                    Path(__file__).resolve().parents[2]/'aic-tactics-protocol-native')).as_posix()
                self.lua.execute('''
package.path=protocol_root..'/?.lua;'..package.path
local scheduled
local function schedule(...) scheduled={...}; return 42 end
local interface={version=1,handler=0x20000000,ring=0x2003c67c,stride=1272,capacity=200,
 writeIndex=0x20109ee0,currentCommand=0x2002d824,localPlayer=0x20109e74,
 tick=0x30000000,receivedParameters=0x20000cdc,scheduleCommand=schedule}
package.loaded['protocols.common']={}
local ownerCalls=0
package.loaded['game.interface']={getNativeCommandInterface=function()
 ownerCalls=ownerCalls+1;return interface
end}
package.loaded['game.version']={setMultiplayerGameVersion=function() end}
package.loaded['game.hooks']={setHooks=function() end}
local owner=dofile(protocol_root..'/init.lua')
modules.protocol=owner
local binding=require('code/native-command')
assert(not pcall(binding.bind,{})) -- enable ordering reaches the actual owner
owner:enable({})
local original=require('code/native-save').bind(require('code/engine-sites').SHC)
local sites=binding.bind(original)
assert(original.commands==nil and original.writeIndexOffset==nil)
assert(sites.commands==interface and sites.writeIndexOffset==0x109ee0 and ownerCalls==1)
realNative.addr=function(address) assert(address==0x1a279c0,'Fixed command binding used'); return 0x31000000 end
local engine=require('code/engine').new(sites)
assert(engine.base==interface.handler and engine.schedule==schedule)
memory[interface.tick]=1234;memory[interface.localPlayer]=6
assert(engine:tick()==1234 and engine:player()==6)
assert(engine.schedule(engine.base,33,4,1000,0x32000000)==42)
assert(#scheduled==5 and scheduled[1]==interface.handler and scheduled[2]==33
 and scheduled[3]==4 and scheduled[4]==1000 and scheduled[5]==0x32000000)
for i=1,100 do engine:tick();engine:player() end
assert(ownerCalls==1)
''')

    def test_missing_or_incompatible_owner_never_returns_fixed_bindings(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime),patch.object(fixture,'LuaRuntime',runtime):
                fixture.RecorderTests.setUp(self)
                self.lua.execute('''
local binding=require('code/native-command')
for _,field in ipairs({'version','handler','ring','stride','capacity','writeIndex',
 'currentCommand','localPlayer','tick','receivedParameters','scheduleCommand'}) do
 local value=commandFixture(); value[field]=0
 modules.protocol={getNativeCommandInterface=function() return value end}
 assert(not pcall(binding.bind,{}),field)
end
modules.protocol={}; assert(not pcall(binding.bind,{}))
modules.protocol=nil; assert(not pcall(binding.bind,{}))
''')
