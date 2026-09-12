import unittest
import ctypes
import os
import tempfile
from pathlib import Path
from lupa.luajit21 import LuaRuntime


class SnapshotCacheTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root=Path(__file__).resolve().parents[1].as_posix()
        self.lua.execute('''
package.path=root..'/?.lua;'..package.path
leases={['ucp/replay-cache/22.lease']=true}; removed={}; attempts={}
package.loaded['code/platform']={mkdir=function() end,identity=function() return {processId=11} end,
 tryTemporaryLease=function(path)
  attempts[#attempts+1]=path
  if leases[path] then return end
  leases[path]=true
  return function() leases[path]=nil end
 end}
ucp={internal={io={files=function()
 return {'11-1.sav','33-1.sav','ucp/replay-cache/33-1.rng.tmp','22-5.sav',
  'readme.txt','33-1.zip','../recordings','ucp/replays/match/start.sav'}
end}}}
os.remove=function(path) removed[path]=true; return true end
cache=require('code/snapshot-cache')
''')

    def test_reclaims_crashed_owners_and_pid_reuse_but_preserves_live_owners(self):
        self.lua.execute('''
assert(cache.allocate()=='ucp/replay-cache/11-1')
assert(removed['ucp/replay-cache/11-1.sav'] and removed['ucp/replay-cache/33-1.sav'])
assert(removed['ucp/replay-cache/33-1.rng.tmp'])
assert(not removed['ucp/replay-cache/22-5.sav'] and not removed['ucp/replay-cache/start.sav'])
assert(not removed['ucp/replay-cache/33-1.zip'])
assert(leases['ucp/replay-cache/11.lease'] and not leases['ucp/replay-cache/33.lease'])
local count=#attempts
assert(cache.allocate()=='ucp/replay-cache/11-2' and #attempts==count)
''')

    def test_cleanup_failure_releases_leases_and_prevents_new_cache_writes(self):
        self.lua.execute('''
os.remove=function() return nil,'access denied',13 end
assert(not pcall(cache.allocate))
assert(not leases['ucp/replay-cache/11.lease'] and not leases['ucp/replay-cache/33.lease'])
os.remove=function(path) removed[path]=true; return true end
assert(cache.allocate()=='ucp/replay-cache/11-1')
''')

    @unittest.skipUnless(os.name=='nt','Requires native Windows file sharing semantics')
    def test_native_lease_excludes_other_owner_and_deletes_on_close(self):
        with tempfile.TemporaryDirectory() as folder:
            lua=LuaRuntime(unpack_returned_tuples=True)
            lua.globals().root=Path(__file__).resolve().parents[1].as_posix()
            lua.globals().lease_path=(Path(folder)/'recorder.lease').as_posix()
            buffers=[]
            def allocate(size,zero):
                buffer=ctypes.create_string_buffer(size); buffers.append(buffer)
                return ctypes.addressof(buffer)
            def write(address,value):
                raw=value.encode('utf-8'); ctypes.memmove(address,raw,len(raw))
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            create=kernel.CreateFileA
            create.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,
                             ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
            create.restype=ctypes.c_void_p
            close=kernel.CloseHandle; close.argtypes=[ctypes.c_void_p]; close.restype=ctypes.c_int
            handles=set()
            def open_lease(*args):
                handle=create(*args)
                if handle==ctypes.c_void_p(-1).value:return -1
                handles.add(handle); return handle
            def close_lease(handle):
                result=close(handle)
                if result:handles.discard(handle)
                return result
            lua.globals().allocate=allocate; lua.globals().write=write
            lua.globals().open_lease=open_lease; lua.globals().close_lease=close_lease
            try:
                lua.execute('''
package.path=root..'/?.lua;'..package.path
core={allocate=allocate,writeString=write}
local platform=require('code/platform')
platform.stdcall=function(library,name,count)
 assert(library=='kernel32.dll')
 if name=='CreateFileA' then assert(count==7); return open_lease end
 assert(name=='CloseHandle' and count==1); return close_lease
end
local release=assert(platform.tryTemporaryLease(lease_path))
assert(not platform.tryTemporaryLease(lease_path))
release(); release()
local again=assert(platform.tryTemporaryLease(lease_path)); again()
''')
                self.assertFalse(Path(folder,'recorder.lease').exists())
                self.assertFalse(handles)
            finally:
                for handle in handles:close(handle)
