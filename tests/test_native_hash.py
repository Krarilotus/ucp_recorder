"""SHA-256 streaming/error paths, plus real Windows CryptoAPI on private buffers.

The Windows adapter translates 32-bit test addresses/handles to this Python
process. The x86 stdcall emitter is independently covered by test_win32_abi.
No game is launched, opened, or modified.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import struct
import unittest
from lupa.luajit21 import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]
COUNTS={'CryptAcquireContextA':5,'CryptCreateHash':5,'CryptHashData':4,
        'CryptGetHashParam':5,'CryptDestroyHash':1,'CryptReleaseContext':2}


class Backend:
    def __init__(self, real=False):
        self.memory=ctypes.create_string_buffer(70000)
        self.base=0x100000
        self.providers={}; self.hashes={}; self.calls=[]
        self.fail=None; self.truncate=False; self.allocated=False
        self.byte_writes=[]; self.broken_bytes=False
        self.real=real
        if real:
            self.api=ctypes.WinDLL('advapi32.dll',use_last_error=True)
            ptr=ctypes.c_void_p; word=ctypes.c_uint32
            signatures={
                'CryptAcquireContextA':[ctypes.POINTER(ptr),ptr,ptr,word,word],
                'CryptCreateHash':[ptr,word,ptr,word,ctypes.POINTER(ptr)],
                'CryptHashData':[ptr,ptr,word,word],
                'CryptGetHashParam':[ptr,word,ptr,ptr,word],
                'CryptDestroyHash':[ptr], 'CryptReleaseContext':[ptr,word]}
            for name,args in signatures.items():
                fn=getattr(self.api,name); fn.argtypes=args; fn.restype=ctypes.c_int

    def pointer(self,address,size=1):
        assert self.base<=address and address+size<=self.base+len(self.memory)
        return ctypes.addressof(self.memory)+address-self.base

    def read(self,address,size):
        return ctypes.string_at(self.pointer(address,size),size)

    def write(self,address,data):
        ctypes.memmove(self.pointer(address,len(data)),data,len(data))

    def integer(self,address):
        return struct.unpack('<I',self.read(address,4))[0]

    def write_integer(self,address,value):
        self.write(address,struct.pack('<I',value&0xffffffff))

    def allocate(self,size,zero):
        assert not self.allocated and size<=len(self.memory) and zero
        self.allocated=True
        return self.base

    def deallocate(self,address):
        assert address==self.base and self.allocated
        self.allocated=False

    def write_bytes(self,address,values):
        data=bytes(values[i] for i in range(1,len(values)+1))
        self.byte_writes.append(len(data))
        if not self.broken_bytes: self.write(address,data)

    def write_string(self,address,value):
        data=value.encode('latin-1')
        self.write(address,data.split(b'\0')[0]+b'\0' if self.truncate else data)

    def bind(self,library,name,count):
        assert library=='advapi32.dll' and count==COUNTS[name]
        def call(*args):
            self.calls.append((name,args))
            assert len(args)==count
            if self.fail==name:
                return 0
            if name=='CryptAcquireContextA':
                out,container,provider,kind,flags=args
                assert container==provider==0 and kind==24 and flags&0xffffffff==0xf0000000
                value=ctypes.c_void_p()
                if self.real:
                    assert self.api.CryptAcquireContextA(ctypes.byref(value),None,None,kind,flags&0xffffffff)
                self.providers[101]=value.value
                self.write_integer(out,101)
            elif name=='CryptCreateHash':
                provider,algorithm,key,flags,out=args
                assert provider in self.providers and algorithm==0x800c and key==flags==0
                value=ctypes.c_void_p()
                if self.real:
                    assert self.api.CryptCreateHash(self.providers[provider],algorithm,None,0,ctypes.byref(value))
                self.hashes[201]=value.value if self.real else hashlib.sha256()
                self.write_integer(out,201)
            elif name=='CryptHashData':
                handle,address,size,flags=args
                assert handle in self.hashes and 0<size<=65536 and flags==0
                if self.real:
                    assert self.api.CryptHashData(self.hashes[handle],self.pointer(address,size),size,0)
                else:
                    self.hashes[handle].update(self.read(address,size))
            elif name=='CryptGetHashParam':
                handle,param,out,size,flags=args
                assert param==2 and self.integer(size)==32 and flags==0
                if self.real:
                    assert self.api.CryptGetHashParam(self.hashes[handle],param,self.pointer(out,32),self.pointer(size,4),0)
                else:
                    self.write(out,self.hashes[handle].digest())
            elif name=='CryptDestroyHash':
                value=self.hashes.pop(args[0])
                if self.real: assert self.api.CryptDestroyHash(value)
            elif name=='CryptReleaseContext':
                value=self.providers.pop(args[0]); assert args[1]==0
                if self.real: assert self.api.CryptReleaseContext(value,0)
            return 1
        return call

    def runtime(self):
        lua=LuaRuntime(encoding='latin-1')
        g=lua.globals(); g.source_root=ROOT.as_posix()
        g.bind=self.bind; g.allocate=self.allocate; g.write_string=self.write_string
        g.deallocate=self.deallocate; g.write_bytes=self.write_bytes
        g.read_string=lambda a,n:self.read(a,n).decode('latin-1')
        g.read_integer=self.integer; g.write_integer=self.write_integer
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/platform']={stdcall=bind}
core={allocate=allocate,deallocate=deallocate,writeBytes=write_bytes,readString=read_string,writeString=write_string,
 readInteger=read_integer,writeInteger=write_integer}
hash=require('code/native-hash')
''')
        return lua


class NativeHashTests(unittest.TestCase):
    def descriptor_runtime(self, data):
        backend=Backend(real=os.name=='nt'); backend.truncate=True
        lua=backend.runtime(); state={'offset':0,'closed':0,'opened':0}
        def read(fd,address,size):
            self.assertEqual(fd,7); self.assertEqual(size,65536)
            if state.get('fail'): return -1
            chunk=data[state['offset']:state['offset']+size]
            state['offset']+=len(chunk); backend.write(address,chunk)
            return len(chunk)
        def close(fd):
            self.assertEqual(fd,7); state['closed']+=1
            return -1 if state.get('close_fail') else 0
        def opened(path,mode,permissions):
            self.assertEqual(path,'ucp/modules/virtual-1.0.0/data.bin')
            self.assertEqual((mode,permissions),(0x8000,0))
            state['offset']=0; state['opened']+=1
            return 4294967295 if state.get('missing') else 7
        def expose(address,count,convention):
            self.assertEqual(convention,0)
            self.assertEqual(count,3 if address==1 else 1)
            return read if address==1 else close
        lua.globals().open_descriptor=opened; lua.globals().expose=expose
        lua.execute('io.openFileDescriptor=open_descriptor; io.ucrt={_read=1,_close=2}; core.exposeCode=expose')
        lua.execute('hash.prepare()')
        backend.byte_writes.clear()
        return backend,lua,state

    def test_framework_descriptor_streams_binary_without_lua_byte_table_round_trip(self):
        data=bytes(range(256))*1025
        backend,lua,state=self.descriptor_runtime(data)
        lua.execute("chunks={}; function chunk(data,count) chunks[#chunks+1]=data; total=count end")
        result=lua.globals().hash.file('ucp/modules/virtual-1.0.0/data.bin',len(data),lua.globals().chunk)
        self.assertEqual(result,hashlib.sha256(data).hexdigest())
        self.assertEqual(lua.eval("table.concat(chunks)").encode('latin-1'),data)
        self.assertEqual(lua.globals().total,len(data))
        self.assertEqual(backend.byte_writes,[])
        self.assertEqual(state['closed'],1)
        self.assertFalse(backend.providers or backend.hashes)

    def test_progress_only_hash_never_copies_native_file_payload_to_lua(self):
        data=bytes(range(256))*1025
        backend,lua,state=self.descriptor_runtime(data)
        lua.execute('''
local read=core.readString
core.readString=function(address,size)
 assert(size==32,'Progress copied a native file payload')
 return read(address,size)
end
progressCounts={}
function progress(count) progressCounts[#progressCounts+1]=count end
''')
        result=lua.globals().hash.file('ucp/modules/virtual-1.0.0/data.bin',len(data),None,lua.globals().progress)
        self.assertEqual(result,hashlib.sha256(data).hexdigest())
        self.assertEqual(list(lua.globals().progressCounts.values()),[65536,131072,196608,262144,len(data)])
        self.assertEqual(state['closed'],1)
        self.assertFalse(backend.providers or backend.hashes)

    def test_descriptor_errors_and_cancellation_close_once_without_leaking_hash_handles(self):
        for fault in ('missing','fail','close_fail','limit','cancel'):
            with self.subTest(fault=fault):
                backend,lua,state=self.descriptor_runtime(b'x'*70000)
                state[fault]=True
                if fault=='cancel':
                    lua.execute('''
local now=0
task=require('code/preparation-task').new(function(progress)
 return hash.file('ucp/modules/virtual-1.0.0/data.bin',70000,nil,function() progress('Hashing') end)
end,function() now=now+20; return now end)
task:step(); assert(task.status=='pending'); task:cancel(); task:step()
assert(task.status=='cancelled')
''')
                else:
                    with self.assertRaises(Exception):
                        lua.globals().hash.file('ucp/modules/virtual-1.0.0/data.bin',69999 if fault=='limit' else 70000)
                self.assertEqual(state['closed'],0 if fault=='missing' else 1)
                self.assertFalse(backend.providers or backend.hashes)

    def check_vectors(self,real,truncate=False):
        backend=Backend(real); backend.truncate=truncate; lua=backend.runtime()
        lua.execute('hash.prepare()')
        for data in [b'',b'abc',b'\0',b'a\0b',b'end\0',bytes(range(256)),
                     *(b'\0'*n for n in (4095,4096,4097,65535,65536,65537)),bytes(range(256))*1025]:
            self.assertEqual(lua.globals().hash.sha256(data.decode('latin-1')),hashlib.sha256(data).hexdigest())
        self.assertFalse(backend.hashes or backend.providers)

        if truncate:
            self.assertTrue(backend.byte_writes)
            self.assertLessEqual(max(backend.byte_writes),4096)
        else:
            self.assertEqual(backend.byte_writes,[])

    def test_legacy_rps_embedded_nuls_startup_and_streaming(self):
        self.check_vectors(False,truncate=True)

    def test_binary_streaming_vectors(self):
        self.check_vectors(False)

    def test_file_hash_streams_without_seeking_and_closes_on_limit_and_read_error(self):
        backend=Backend(); lua=backend.runtime()
        lua.execute('''
closed=0
io.open=function()
 local remaining=70000
 return {read=function(_,n)
   if failRead then return nil,'disk read failed' end
   if remaining==0 then return end
   local size=math.min(n,remaining); remaining=remaining-size; return string.rep('x',size)
 end,close=function() closed=closed+1; return true end}
end
''')
        self.assertEqual(lua.globals().hash.file('virtual',70000),hashlib.sha256(b'x'*70000).hexdigest())
        with self.assertRaisesRegex(Exception,'size limit'):
            lua.globals().hash.file('virtual',69999)
        lua.execute('failRead=true')
        with self.assertRaisesRegex(Exception,'disk read failed'):
            lua.globals().hash.file('virtual',70000)
        self.assertEqual(lua.globals().closed,3)
        self.assertFalse(backend.hashes or backend.providers)

    def test_yielding_preparation_cancel_releases_native_hash_and_file(self):
        backend=Backend(real=os.name=='nt'); lua=backend.runtime()
        lua.execute('''
local Task=require('code/preparation-task'); local now=0
closed=0
io.open=function()
 local remaining=200000
 return {read=function(_,n)
  if remaining==0 then return end
  local count=math.min(n,remaining); remaining=remaining-count; return string.rep('x',count)
 end,close=function() closed=closed+1; return true end}
end
task=Task.new(function(progress)
 return hash.file('virtual',200000,function() progress('Hashing') end)
end,function() now=now+20; return now end)
task:step(); assert(task.status=='pending' and closed==0)
''')
        self.assertTrue(backend.providers and backend.hashes)
        lua.execute("task:cancel(); task:step(); assert(task.status=='cancelled' and closed==1)")
        self.assertFalse(backend.providers or backend.hashes)
        self.assertEqual(lua.globals().hash.sha256('abc'),hashlib.sha256(b'abc').hexdigest())

    @unittest.skipUnless(os.name=='nt','Requires Windows CryptoAPI')
    def test_actual_windows_cryptoapi_private_buffers(self):
        self.check_vectors(True)
        self.check_vectors(True,truncate=True)

    def test_each_failure_releases_handles_and_allows_retry(self):
        for name in ['CryptAcquireContextA','CryptCreateHash','CryptHashData','CryptGetHashParam']:
            with self.subTest(name=name):
                backend=Backend(); lua=backend.runtime(); backend.fail=name
                with self.assertRaises(Exception): lua.globals().hash.sha256('test')
                self.assertFalse(backend.providers or backend.hashes)
                backend.fail=None
                self.assertEqual(lua.globals().hash.sha256('abc'),hashlib.sha256(b'abc').hexdigest())
                self.assertFalse(backend.providers or backend.hashes)

    def test_broken_binary_fallback_is_rejected_before_opening_provider(self):
        backend=Backend(); backend.truncate=True; backend.broken_bytes=True; lua=backend.runtime()
        with self.assertRaisesRegex(Exception,'Binary memory transfer verification failed'):
            lua.execute('hash.prepare()')
        self.assertEqual(backend.calls,[])
        self.assertFalse(backend.allocated)


if __name__=='__main__': unittest.main()
