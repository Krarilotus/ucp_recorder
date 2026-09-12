"""Native thread ABI and ownership; Windows scheduling/codec are separate boundaries."""
import struct
import unittest
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg
import test_recorder as fixture


class CodecWorkerTests(unittest.TestCase):
    check=fixture.RecorderTests.check
    setUp=fixture.RecorderTests.setUp

    def test_native_worker_preserves_thread_abi_private_rows_and_cancellation(self):
        code=self.lua.eval("require('code/codec-worker').code()")
        machine=Uc(UC_ARCH_X86,UC_MODE_32); machine.mem_map(0x1000,0x10000)
        machine.mem_write(0x1000,bytes(code.values())); machine.mem_write(0x5000,b'\xc2\x14\x00')
        def put(a,v): machine.mem_write(a,struct.pack('<I',v))
        def get(a): return struct.unpack('<I',machine.mem_read(a,4))[0]
        calls=[]; cancel=False
        def codec(uc,ip,size,context):
            sp=uc.reg_read(reg.UC_X86_REG_ESP)
            args=[get(sp+4+i*4) for i in range(5)]
            calls.append(args)
            assert uc.reg_read(reg.UC_X86_REG_ECX)==0x4000
            crc,length,source,output,count=args
            assert source==0x7000+(len(calls)-1)*2000 and count==1000
            put(crc,0x12345678); put(length,42)
            uc.reg_write(reg.UC_X86_REG_EAX,1)
            if cancel: put(0x3010,1)
        machine.hook_add(UC_HOOK_CODE,codec,begin=0x5000,end=0x5000)
        for cancel in (False,True):
            calls.clear(); put(0x3000,3); put(0x3004,0x3100); put(0x3008,0x4000)
            put(0x300c,0x5000); put(0x3010,0)
            for i in range(3):
                machine.mem_write(0x3100+i*28,struct.pack('<7I',0x7000+i*1000,0x9000+i*1000,1000,0,0,0,int(i!=1)))
            preserved={reg.UC_X86_REG_EBX:11,reg.UC_X86_REG_EBP:22,reg.UC_X86_REG_ESI:33,reg.UC_X86_REG_EDI:44}
            for key,v in preserved.items(): machine.reg_write(key,v)
            machine.reg_write(reg.UC_X86_REG_ESP,0xe000); put(0xe000,0xf000); put(0xe004,0x3000)
            machine.emu_start(0x1000,0xf000,count=1000)
            self.assertEqual(len(calls),1 if cancel else 2)
            self.assertEqual(machine.reg_read(reg.UC_X86_REG_ESP),0xe008)
            self.assertTrue(all(machine.reg_read(key)==v for key,v in preserved.items()))
            self.assertEqual(get(0x3100+28+12),0)
            self.assertEqual(get(0x3100+12),1)

    def test_pending_thread_cannot_release_buffers_and_failure_releases_allocation(self):
        self.check('''
local wait=258; local create=99; local freed,closed=0,0
core.deallocate=function() freed=freed+1 end
require('code/platform').stdcall=function(_,name)
 if name=='CreateThread' then return function() return create end end
 if name=='WaitForSingleObject' then return function(handle,timeout) assert(handle==99 and timeout==0); return wait end end
 if name=='CloseHandle' then return function(handle) assert(handle==99); closed=closed+1; return 1 end end
 return function() return 1 end
end
local worker=require('code/codec-worker')
local job=worker.new({{address=1000,size=2000,compress=true}},5000)
assert(not job:ready() and not pcall(job.close,job) and freed==0)
job:cancel(); assert(memory[job.memory+16]==1)
wait=0; assert(job:ready() and closed==1)
job:close(); assert(freed==1 and closed==1)
create=0; assert(not pcall(worker.new,{{address=1000,size=2000,compress=true}},5000))
assert(freed==2)
''')
