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

    def write_string(self,address,value):
        data=value.encode('latin-1')
        self.write(address,data.split(b'\0')[0] if self.truncate else data)

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
        g.read_string=lambda a,n:self.read(a,n).decode('latin-1')
        g.read_integer=self.integer; g.write_integer=self.write_integer
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/platform']={stdcall=bind}
core={allocate=allocate,readString=read_string,writeString=write_string,
 readInteger=read_integer,writeInteger=write_integer}
hash=require('code/native-hash')
''')
        return lua


class NativeHashTests(unittest.TestCase):
    def check_vectors(self,real):
        backend=Backend(real); lua=backend.runtime()
        lua.execute('hash.prepare()')
        for data in [b'',b'abc',bytes(range(256)),bytes(range(256))*1025]:
            self.assertEqual(lua.globals().hash.sha256(data.decode('latin-1')),hashlib.sha256(data).hexdigest())
        self.assertFalse(backend.hashes or backend.providers)

    def test_binary_streaming_vectors(self):
        self.check_vectors(False)

    @unittest.skipUnless(os.name=='nt','Requires Windows CryptoAPI')
    def test_actual_windows_cryptoapi_private_buffers(self):
        self.check_vectors(True)

    def test_each_failure_releases_handles_and_allows_retry(self):
        for name in ['CryptAcquireContextA','CryptCreateHash','CryptHashData','CryptGetHashParam']:
            with self.subTest(name=name):
                backend=Backend(); lua=backend.runtime(); backend.fail=name
                with self.assertRaises(Exception): lua.globals().hash.sha256('test')
                self.assertFalse(backend.providers or backend.hashes)
                backend.fail=None
                self.assertEqual(lua.globals().hash.sha256('abc'),hashlib.sha256(b'abc').hexdigest())
                self.assertFalse(backend.providers or backend.hashes)

    def test_truncating_framework_is_rejected_before_opening_provider(self):
        backend=Backend(); backend.truncate=True; lua=backend.runtime()
        with self.assertRaisesRegex(Exception,'binary string writes'):
            lua.execute('hash.prepare()')
        self.assertEqual(backend.calls,[])


if __name__=='__main__': unittest.main()
