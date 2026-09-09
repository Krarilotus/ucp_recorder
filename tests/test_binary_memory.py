"""Binary-copy capability selection, using private LuaJIT FFI buffers only."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]


class BinaryMemoryTests(unittest.TestCase):
    def runtime(self,mode='working'):
        lua=LuaRuntime(encoding='latin-1')
        lua.globals().source_root=ROOT.as_posix()
        lua.globals().mode=mode
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
local ffi=require('ffi')
local allocations={}
copies,byteWrites,freed=0,0,0
core={
 allocate=function(size)
  local data=ffi.new('uint8_t[?]',size)
  local address=tonumber(ffi.cast('uintptr_t',data))
  allocations[address]=data; return address
 end,
 deallocate=function(address) assert(allocations[address]); allocations[address]=nil; freed=freed+1 end,
 readString=function(address,size) return ffi.string(ffi.cast('void *',address),size) end,
 writeString=function(address,data)
  local zero=data:find('\0',1,true)
  data=data:sub(1,zero and zero-1 or #data)
  ffi.copy(ffi.cast('void *',address),data,#data+1)
 end,
 writeBytes=function(address,values)
  byteWrites=byteWrites+1
  local p=ffi.cast('uint8_t *',address)
  for i,value in ipairs(values) do p[i-1]=value end
 end}
modules={cffi={cffi=function()
 if mode=='missing' then return {} end
 if mode=='throws' then error('Unsupported CFFI bridge') end
 return {cast=ffi.cast,copy=function(address,data,length)
  copies=copies+1
  if mode=='noop' then return end
  if mode=='truncates' then length=(data:find('\0',1,true) or (#data+1))-1 end
  ffi.copy(address,data,length)
  if mode=='writes_then_throws' then error('Copy failed after writing') end
 end}
end}}
binary=require('code/binary-memory')
function check()
 binary.prepare()
 local values={}; for i=0,255 do values[#values+1]=string.char(i) end
 local all=table.concat(values):rep(300)
 local address=core.allocate(#all+2)
 for _,size in ipairs({0,1,255,256,4095,4096,4097,65535,65536,#all}) do
  local data=all:sub(1,size)
  local p=ffi.cast('uint8_t *',address)
  p[size]=0xa5; p[size+1]=0x5a
  binary.write(address,data)
  assert(core.readString(address,size)==data)
  assert(p[size]==0xa5 and p[size+1]==0x5a,'Length-explicit copy overflow')
 end
 core.deallocate(address)
end
''')
        return lua

    def test_real_ffi_binary_copy_without_byte_tables_or_terminator(self):
        lua=self.runtime(); lua.execute('check()')
        self.assertEqual(lua.globals().byteWrites,0)
        self.assertGreater(lua.globals().copies,10)
        self.assertEqual(lua.globals().freed,2)

    def test_unavailable_or_faulty_optional_bridge_uses_verified_fallback(self):
        for mode in ('missing','throws','noop','truncates','writes_then_throws'):
            with self.subTest(mode=mode):
                lua=self.runtime(mode); lua.execute('check()')
                self.assertGreater(lua.globals().byteWrites,0)
                self.assertEqual(lua.globals().freed,2)


if __name__=='__main__':unittest.main()
