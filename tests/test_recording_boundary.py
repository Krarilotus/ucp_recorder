"""Execute the production native copy: exact bytes, ownership and x86 ABI."""
import struct
import unittest
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn import x86_const as reg
import test_recorder as fixture


class RecordingBoundaryTests(unittest.TestCase):
    def test_lua54_emits_integer_bytes_required_by_rps(self):
        from lupa.lua54 import LuaRuntime
        lua=LuaRuntime()
        lua.globals().source_root=fixture.ROOT.as_posix()
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
core={allocate=function() return 0x300000 end,allocateCode=function() return 0x400000 end,
 writeCode=function(_,code)
   for _,byte in ipairs(code) do assert(math.type(byte)=='integer' and byte>=0 and byte<=255) end
 end,exposeCode=function() return function() end end}
require('code/recording-boundary').new({rng=0x100000,sites={playerResources=0x200000}})
''')

    def test_native_capture_preserves_sources_registers_and_last_observed_boundary(self):
        fixture.RecorderTests.setUp(self)
        machine=Uc(UC_ARCH_X86,UC_MODE_32)
        machine.mem_map(0x100000,0x500000)
        rng,resources,buffer,code,stack,stop=0x100000,0x200000,0x300000,0x400000,0x500000,0x510000
        allocations=[]; reads=[]
        def allocate(size,zero):
            allocations.append(size)
            machine.mem_write(buffer-1,b'!'+b'\0'*size+b'!')
            return buffer
        def write_code(address,values):
            machine.mem_write(address,bytes(values.values()))
        def read(address,size):
            reads.append((address,size))
            return bytes(machine.mem_read(address,size))
        registers={getattr(reg,'UC_X86_REG_'+name):value for name,value in
                   [('EAX',11),('EBX',22),('ECX',33),('EDX',44),('ESI',55),('EDI',66),('EBP',77)]}
        def expose(address,count,convention):
            self.assertEqual((address,count,convention),(code,0,0))
            def run():
                for key,value in registers.items(): machine.reg_write(key,value)
                machine.reg_write(reg.UC_X86_REG_EFLAGS,0x602)  # direction flag set on entry
                machine.reg_write(reg.UC_X86_REG_ESP,stack)
                machine.mem_write(stack,struct.pack('<I',stop))
                machine.emu_start(code,stop,count=20000)
                self.assertEqual(machine.reg_read(reg.UC_X86_REG_ESP),stack+4)
                self.assertEqual(machine.reg_read(reg.UC_X86_REG_EFLAGS),0x602)
                for key,value in registers.items(): self.assertEqual(machine.reg_read(key),value)
            return run
        core=self.lua.globals().core
        core.allocate=allocate; core.allocateCode=lambda size: code
        core.writeCode=write_code; core.exposeCode=expose; core.readString=read
        core.readSmallInteger=lambda address: struct.unpack('<H',machine.mem_read(address,2))[0]
        core.readInteger=lambda address: struct.unpack('<i',machine.mem_read(address,4))[0]
        self.lua.execute('''
boundary=require('code/recording-boundary').new({rng=0x100000,sites={playerResources=0x200000}})
assert(not pcall(boundary.read,boundary))
assert(not pcall(boundary.rngState,boundary))
''')
        for index in (1,2):
            expected_rng=struct.pack('<HH',index,22)+b'x'*40004+struct.pack('<ii',3,4)
            machine.mem_write(rng,expected_rng)
            expected_resources=b''
            for player in range(1,9):
                data=bytes([64+player+index])*100
                machine.mem_write(resources+player*0x39f4-1,b'!'+data+b'!')
                expected_resources+=data
            reads.clear()
            self.lua.execute('boundary:capture()')
            self.assertEqual(reads,[])  # no Lua strings/materialization on the hot path
            self.assertEqual(bytes(machine.mem_read(rng,40016)),expected_rng)
            for player in range(1,9):
                self.assertEqual(bytes(machine.mem_read(resources+player*0x39f4-1,102)),
                                 b'!'+bytes([64+player+index])*100+b'!')
            machine.mem_write(rng,b'z'*40016)
            for player in range(1,9): machine.mem_write(resources+player*0x39f4,b'z'*100)
            actual_rng,actual_resources=self.lua.eval('boundary:read()')
            self.assertEqual(actual_rng.encode(),expected_rng)
            self.assertEqual(actual_resources.encode(),expected_resources)
            self.assertEqual(list(self.lua.eval('boundary:rngState()').values()),[index,22,3,4])
            self.assertEqual(bytes(machine.mem_read(buffer-1,1)),b'!')
            self.assertEqual(bytes(machine.mem_read(buffer+40816,2)),b'\0!')
            self.lua.execute('boundary:clear(); assert(not pcall(boundary.read,boundary))')
        self.assertEqual(allocations,[40817])


if __name__=='__main__': unittest.main()
