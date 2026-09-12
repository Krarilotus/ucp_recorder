"""Use the framework capability when present; never retry after its rejection."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class UniqueContextTests(unittest.TestCase):
    def test_framework_owner_and_current_bytes_remain_authoritative(self):
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                lua=runtime();lua.globals().root=ROOT.as_posix()
                lua.execute('''
package.path=root..'/?.lua;'..package.path
local calls=0
core={AOBScan=function() error('legacy scan used') end,
 scanForAOB=function() error('legacy second scan used') end,
 readBytes=function(address,count) assert(address==0x10000000 and count==2);return {0x53,0x56} end,
 AOBScanUnique=function(pattern,label)
 assert(pattern=='53 56' and label=='fixture');calls=calls+1;return 0x10000000 end}
local resolver=require('code/hook-check')
local site=resolver.resolve('53 56','fixture')
assert(site.address==0x10000000 and #site.bytes==2 and calls==1)
core.readBytes=function() return {0xcc,0x56} end
assert(not pcall(resolver.resolve,'53 56','fixture'))
for _,failure in ipairs({'missing','ambiguous','inaccessible'}) do
 core.AOBScanUnique=function() error(failure) end
 local ok,reason=pcall(resolver.resolve,'53 56','fixture')
 assert(not ok and tostring(reason):find(failure,1,true))
end
for _,value in ipairs({0,false,-1}) do
 core.AOBScanUnique=function() return value end
 assert(not pcall(resolver.resolve,'53 56','fixture'))
end
''')
