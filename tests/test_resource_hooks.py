"""Resource leaf hooks must preserve the game's nonstandard live ECX/EDX."""
from pathlib import Path
import struct
import unittest
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX,
                              UC_X86_REG_ESP, UC_X86_REG_EFLAGS, UC_X86_REG_EIP)

ROOT = Path(__file__).resolve().parents[1]


class ResourceHookTests(unittest.TestCase):
    def test_normal_and_overridden_leaf_calls_preserve_native_registers(self):
        lua = LuaRuntime()
        lua.globals().root = ROOT.as_posix()
        lua.execute("package.path=root..'/?.lua;'..package.path")
        emitter = lua.eval("require('code/resource-hooks')")
        sites = lua.eval("require('code/engine-sites')")
        original = {
            'mapName': bytes.fromhex('8b4424043df40100007c0533c0c2040069c0e90300008d8408c80b0000c20400'),
            'fileName': bytes.fromhex('8b81c40b000069c0e90300008d8408e0ae0700c3'),
        }
        for variant in ('SHC', 'Extreme'):
            for name, code in original.items():
                for enabled in (0, 1):
                    for index in (0, 1, 14, 499, 500):
                        for flags in (0x202, 0x242, 0x282, 0xa82):
                            with self.subTest(variant=variant, name=name, enabled=enabled, index=index, flags=flags):
                                results = []
                                for gated in (False, True):
                                    cpu = Uc(UC_ARCH_X86, UC_MODE_32)
                                    cpu.mem_map(0x400000, 0x400000)
                                    site = sites[variant][name]
                                    cpu.mem_write(site.address, code)
                                    cpu.mem_write(0x600000, struct.pack('<I', enabled))
                                    cpu.mem_write(0x601bc4, struct.pack('<I', index))
                                    cpu.mem_write(0x700000, struct.pack('<II', 0x710000, index))
                                    if gated:
                                        bridge = bytes(emitter.build(site, 0x600000, 0x620000, name == 'fileName', 0x500000).values())
                                        cpu.mem_write(0x500000, bridge)
                                        cpu.mem_write(site.address, b'\xe9' + struct.pack('<i', 0x500000-site.address-5))
                                    for reg, value in ((UC_X86_REG_ECX, 0x601000), (UC_X86_REG_EDX, 0x623456),
                                                       (UC_X86_REG_ESP, 0x700000), (UC_X86_REG_EFLAGS, flags)):
                                        cpu.reg_write(reg, value)
                                    cpu.emu_start(site.address, 0x710000, count=1000)
                                    self.assertEqual(cpu.reg_read(UC_X86_REG_EIP), 0x710000)
                                    self.assertEqual(cpu.reg_read(UC_X86_REG_ECX), 0x601000)
                                    self.assertEqual(cpu.reg_read(UC_X86_REG_EDX), 0x623456)
                                    self.assertEqual(cpu.reg_read(UC_X86_REG_ESP), 0x700004 if name == 'fileName' else 0x700008)
                                    results.append((cpu.reg_read(UC_X86_REG_EAX), cpu.reg_read(UC_X86_REG_EFLAGS)))
                                if enabled and (name == 'mapName' or index == 1):
                                    self.assertEqual(results[1], (0x620000, flags))
                                else:
                                    self.assertEqual(*results)
