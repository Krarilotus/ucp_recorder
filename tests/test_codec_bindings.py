"""Codec capability discovery is independent of the executable address layout."""
from pathlib import Path
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT = Path(__file__).resolve().parents[1]


class CodecBindingTests(unittest.TestCase):
    def fixture(self, runtime):
        lua = runtime(unpack_returned_tuples=True)
        lua.globals().source_root = ROOT.as_posix()
        lua.execute("""
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/binary-memory']={prepare=function() end}
codec=require('code/world-codec')
local function upvalue(fn,key)
 for i=1,30 do
  local name,value=debug.getupvalue(fn,i)
  if name==key then return value end
 end
 error('Missing upvalue '..key)
end
local prepare=upvalue(codec.compressorAddress,'prepare')
patterns=upvalue(prepare,'contexts')
expected={implode=0x10100000,explode=0x20100000}
local addresses,bytes={},{}
for name,pattern in pairs(patterns) do
 local address=expected[name]; addresses[pattern]=address
 local i=0
 for token in pattern:gmatch('%S+') do
  bytes[address+i]=token=='?' and 0x19 or tonumber(token,16); i=i+1
 end
end
scans=0; exposed=0
core={
 AOBScan=function(pattern) scans=scans+1; return addresses[pattern] end,
 scanForAOB=function(pattern,start) scans=scans+1; assert(start==addresses[pattern]+1); return 0 end,
 readBytes=function(a,n) local t={};for i=1,n do t[i]=bytes[a+i-1] end;return t end,
 exposeCode=function(a,n,abi)
  assert((a==expected.implode or a==expected.explode) and n==6 and abi==1)
  exposed=exposed+1; return function() end
 end,
}
function changeByte(a) bytes[a]=0xcc end
""")
        return lua

    def test_relocated_thiscall_bindings_resolve_once_without_native_profile(self):
        for runtime in (Lua54, LuaJIT):
            with self.subTest(runtime=runtime):
                self.fixture(runtime).execute("""
assert(codec.compressorAddress()==expected.implode)
assert(scans==4 and exposed==2)
for i=1,100 do assert(codec.compressorAddress()==expected.implode) end
assert(scans==4 and exposed==2)
""")

    def test_missing_ambiguous_and_occupied_capabilities_expose_nothing(self):
        for runtime in (Lua54, LuaJIT):
            for name in ('implode', 'explode'):
                cases = (
                    f"local old=core.AOBScan; core.AOBScan=function(p) if p==patterns.{name} then return 0 end; return old(p) end",
                    f"local old=core.scanForAOB; core.scanForAOB=function(p,a) if p==patterns.{name} then return a+1024 end; return old(p,a) end",
                    f"changeByte(expected.{name})",
                    # After the short prologue, including the stack cleanup.
                    f"changeByte(expected.{name}+35)",
                )
                for case in cases:
                    with self.subTest(runtime=runtime, name=name, case=case):
                        self.fixture(runtime).execute(case+"; assert(not pcall(codec.compressorAddress)); assert(exposed==0)")
