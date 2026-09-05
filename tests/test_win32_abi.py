"""Emulate the generated 32-bit stdcall bridge; never call Windows or game code."""
from pathlib import Path
import struct
import unittest

from lupa.luajit21 import LuaRuntime

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBP, UC_X86_REG_EAX
except ImportError:
    Uc = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(Uc is None, 'Install unicorn==2.1.4 for 32-bit ABI emulation')
class Win32ABITests(unittest.TestCase):
    def test_generated_bridges_preserve_argument_order_and_caller_stack(self):
        for count in (0, 1, 2, 3, 6, 8, 10):
            with self.subTest(arguments=count):
                lua = LuaRuntime()
                lua.execute('''
core={
 callTo=function(address) return {target=address} end,
 calculateCodeSize=function(code) return #code+4 end,
 allocateCode=function(size) assert(type(size)=='number'); allocated=size; return 0x100000 end,
 writeCode=function(address,code) assert(address==0x100000); captured=code end,
 exposeCode=function(address,count,convention) return {address,count,convention} end,
}
''')
                platform = lua.execute((ROOT/'code/platform.lua').read_text())
                bridge = platform.stdcallAddress(0x102000, count)
                self.assertEqual(list(bridge.values()), [0x100000, count, 0])
                code = bytearray()
                for instruction in lua.globals().captured.values():
                    if isinstance(instruction, int):
                        code.append(instruction)
                    else:
                        code += b'\xe8'+struct.pack('<i', instruction['target']-(0x100000+len(code)+5))
                self.assertEqual(len(code), lua.globals().allocated)
                emulator = Uc(UC_ARCH_X86, UC_MODE_32)
                emulator.mem_map(0x100000, 0x4000)
                emulator.mem_map(0x200000, 0x2000)
                emulator.mem_write(0x100000, bytes(code))
                emulator.mem_write(0x102000, b'\xb8\x2a\0\0\0\xc2'+struct.pack('<H', count*4))
                arguments = [0x100+i for i in range(count)]
                emulator.mem_write(0x201000, struct.pack('<'+'I'*(count+1), 0x103000, *arguments))
                emulator.reg_write(UC_X86_REG_ESP, 0x201000)
                emulator.reg_write(UC_X86_REG_EBP, 0x12345678)
                observed = []

                def callee(machine, address, size, unused):
                    if address == 0x102000:
                        stack = machine.reg_read(UC_X86_REG_ESP)
                        observed.extend(struct.unpack('<'+'I'*count, machine.mem_read(stack+4, count*4)))

                emulator.hook_add(UC_HOOK_CODE, callee)
                emulator.emu_start(0x100000, 0x103000, count=1000)
                self.assertEqual(observed, arguments)
                self.assertEqual(emulator.reg_read(UC_X86_REG_ESP), 0x201004)
                self.assertEqual(emulator.reg_read(UC_X86_REG_EBP), 0x12345678)
                self.assertEqual(emulator.reg_read(UC_X86_REG_EAX), 42)
