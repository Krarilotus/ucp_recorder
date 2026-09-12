"""Run generated observers in x86; native callees remain observable stand-ins."""
import struct
import unittest
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg
from test_scoped_code import ROOT, REGS


class MaintenanceNativeTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.globals().source_root = ROOT.as_posix()
        self.lua.execute("package.path=source_root..'/?.lua;'..package.path")
        self.emitter = self.lua.eval("require('code/scoped-code')")
        self.profiles = self.lua.eval("require('tests/fixtures/maintenance-sites')")

    def run_observer(self, variant, kind, *, active=1, mode=99, tick=11,
                     previous=11, count=0, unclocked=0, flags=0xa83):
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(0x400000, 0x3000000)
        machine.mem_map(0x4000000, 0x20000)
        state, clock, mode_pointer, callback, origin = 0x600100, 0x600180, 0x600184, 0x4001000, 0x4000000
        put = lambda a, v: machine.mem_write(a, struct.pack('<I', v & 0xffffffff))
        get = lambda a: struct.unpack('<I', machine.mem_read(a, 4))[0]
        for offset, value in ((0, active), (4, previous), (8, count), (16, unclocked)):
            put(state + offset, value)
        put(clock, tick); put(mode_pointer, mode)
        site = self.profiles[variant][kind]
        site['state'], site['clock'], site['callback'] = state, clock, callback
        site['patch'] = 'maintenanceCount' if kind == 'maintenance' else 'unclockedWorld'
        site['kind'] = 'raw' if kind == 'maintenance' else 'prefixCall'
        code = self.emitter.build(site, state, mode_pointer, None, origin)
        machine.mem_write(origin, bytes(code.values()))
        machine.mem_write(site['address'], bytes(self.emitter.jump(site['address'], origin, len(site['bytes'])).values()))
        stack = 0x4018000
        initial = [0x500000, 0x600010, 0x600000, 0x20, 0x600000, 0xabcdef00, 0x401f000, stack, flags]
        for register, value in zip(REGS, initial): machine.reg_write(register, value)
        observed = []
        stop = site['address'] + len(site['bytes'])

        def observe(uc, ip, size, unused):
            if ip == stop: uc.emu_stop()
            elif ip == callback or ip == site['target']:
                observed.append((ip, get(state + 8)))
                # The Lua callback can clobber volatile registers and flags;
                # its wrapper must restore them before the original callee.
                if ip == callback:
                    for r in (reg.UC_X86_REG_EAX, reg.UC_X86_REG_ECX, reg.UC_X86_REG_EDX):
                        uc.reg_write(r, 0x9876)
                    uc.reg_write(reg.UC_X86_REG_EFLAGS, 0x202)
                sp = uc.reg_read(reg.UC_X86_REG_ESP)
                uc.reg_write(reg.UC_X86_REG_EIP, get(sp))
                uc.reg_write(reg.UC_X86_REG_ESP, sp + 4)

        machine.hook_add(UC_HOOK_CODE, observe)
        machine.emu_start(site['address'], stop, count=500)
        self.assertEqual(machine.reg_read(reg.UC_X86_REG_EIP), stop)
        expected = initial[:]
        expected[2] = struct.unpack('<I', bytes(site['bytes'].values())[1:5])[0] if kind == 'maintenance' else initial[4]
        self.assertEqual([machine.reg_read(r) for r in REGS], expected)
        if kind == 'world': self.assertEqual(observed[-1][0], site['target'])
        return [get(state + i) for i in (4, 8, 12, 16)], observed

    def test_clocked_and_unclocked_passes_preserve_original_machine_contract(self):
        for variant in ('SHC', 'Extreme'):
            for flags in (0x202, 0xa83):
                for mode in (0, 99):
                    with self.subTest(variant=variant, flags=flags, mode=mode):
                        state, calls = self.run_observer(variant, 'maintenance', mode=mode, flags=flags, count=6)
                        self.assertEqual(state, [11, 7, 0, 1]); self.assertEqual(calls, [])
                        state, _ = self.run_observer(variant, 'maintenance', mode=mode, flags=flags, previous=10, count=6, unclocked=1)
                        self.assertEqual(state, [11, 6, 0, 0])
                        state, calls = self.run_observer(variant, 'world', mode=mode, flags=flags, count=7, unclocked=1)
                        self.assertEqual(state, [11, 6, 0, 1]); self.assertEqual(calls[0][1], 6)
                        self.assertEqual(len(calls), 2)

    def test_idle_and_multiplayer_never_capture_or_change_phase_state(self):
        for variant in ('SHC', 'Extreme'):
            for kind in ('maintenance', 'world'):
                for active, mode in ((0, 99), (0, 0), (1, 1), (1, 2), (1, 0xffffffff)):
                    with self.subTest(variant=variant, kind=kind, active=active, mode=mode):
                        state, calls = self.run_observer(variant, kind, active=active, mode=mode, count=7, unclocked=1)
                        self.assertEqual(state, [11, 7, 0, 1])
                        self.assertEqual(len(calls), int(kind == 'world'))

    def test_overflow_is_reported_without_wrapping_and_normal_world_has_no_callback(self):
        for variant in ('SHC', 'Extreme'):
            state, _ = self.run_observer(variant, 'maintenance', count=2147483647)
            self.assertEqual(state, [11, 2147483647, 1, 1])
            state, calls = self.run_observer(variant, 'world', count=0, unclocked=1)
            self.assertEqual(state, [11, 0, 1, 1]); self.assertEqual(len(calls), 2)
            state, calls = self.run_observer(variant, 'world', count=3)
            self.assertEqual(state, [11, 3, 0, 0]); self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
