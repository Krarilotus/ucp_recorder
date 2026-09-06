"""Diagnostics must load with UCP's extension-local require, not host LuaJIT modules."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT


class RuntimeTests(unittest.TestCase):
    def test_extension_only_require_and_checksum_agree_across_runtimes(self):
        source=(Path(__file__).resolve().parents[1]/'code/rng-attribution.lua').read_text(encoding='utf-8')
        expected=0
        for tick in range(1,10001):
            expected=(((expected*33+0xffffffff)*33+tick)*33+2)%4294967296
        for runtime in (Lua54,LuaJIT):
            with self.subTest(runtime=runtime):
                lua=runtime(unpack_returned_tuples=True)
                lua.execute('''
require=function(name)
 assert(name=='code/sessions' or name=='code/platform' or name=='code/native',
  'Unavailable extension dependency: '..name)
 return {}
end
core={readInteger=function() return -1 end}
now=1
engine={singlePlayer=function() return true end,tick=function() return now end}
''')
                lua.globals().Attribution=lua.execute(source)
                lua.execute('''
trace=Attribution.new(engine); trace.file=true; trace:clear()
for i=1,10000 do now=i; trace:observe('rngCall',2,100) end
assert(trace.count==10000 and not trace.failed)
''')
                self.assertEqual(lua.globals().trace.order,expected)
