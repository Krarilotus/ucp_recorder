"""Compare generated native gates to the original instruction sequences in x86.

The callee stand-in makes calls observable; no game process is launched.
"""
from pathlib import Path
import struct
import unittest
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EFLAGS, UC_X86_REG_EIP)

ROOT=Path(__file__).resolve().parents[1]
REGS=[UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,
      UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP,UC_X86_REG_EFLAGS]


class ScopedCodeTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime()
        self.emitter=self.lua.execute((ROOT/'code/scoped-code.lua').read_text())
        self.profiles=self.lua.execute((ROOT/'code/scoped-sites.lua').read_text())

    def run_code(self,site,enabled,mode,flags,gated,halt=0):
        machine=Uc(UC_ARCH_X86,UC_MODE_32)
        machine.mem_map(0x400000,0x3000000)
        machine.mem_map(0x4000000,0x1000)
        machine.mem_map(0x4100000,0x10000)
        original=bytes(site['bytes'].values())
        machine.mem_write(site['address'],original)
        counter,scope,mode_pointer=0x600100,0x600104,0x600108
        def put(address,value): machine.mem_write(address,struct.pack('<I',value&0xffffffff))
        put(scope,enabled); put(mode_pointer,mode)
        if site['patch']=='tick':
            put(site['halt'],halt)
            machine.mem_write(site['callback'],b'\xff\x05'+struct.pack('<I',counter)+b'\xb8\x01\0\0\0\xc3')
            if site['originalCallback']:
                machine.mem_write(site['originalCallback'],b'\xff\x05'+struct.pack('<I',counter)
                    + b'\xb8\x11\0\0\0\xb9\x22\0\0\0\xba\x33\0\0\0\xc3')
        if gated:
            gate=bytes(self.emitter.build(site,scope,mode_pointer,123,0x4000000).values())
            machine.mem_write(0x4000000,gate)
            machine.mem_write(site['address'],bytes(self.emitter.jump(site['address'],0x4000000,len(original)).values()))
        if site['kind']=='call':
            ret=b'\xc2\x2c\0' if site['patch']=='cleanup' else b'\xc3'
            machine.mem_write(site['target'],b'\xff\x05'+struct.pack('<I',counter)+b'\xb8\x01\0\0\0'+ret)
        initial=[0x500000,0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000,0x4108000,flags]
        for register,value in zip(REGS,initial): machine.reg_write(register,value)
        stops={site['address']+len(original)}
        if site['kind']=='branch': stops.add(site['target'])
        if site['patch']=='tick': stops.add(site['skipTick'])
        def stop(uc,address,size,data):
            if address in stops: uc.emu_stop()
        machine.hook_add(UC_HOOK_CODE,stop)
        machine.emu_start(site['address'],0,count=1000)
        self.assertIn(machine.reg_read(UC_X86_REG_EIP),stops)
        return tuple(machine.reg_read(r) for r in REGS)+(machine.reg_read(UC_X86_REG_EIP),
            struct.unpack('<I',machine.mem_read(counter,4))[0],struct.unpack('<I',machine.mem_read(0x600004,4))[0])

    def test_multiplayer_and_idle_paths_match_original_registers_flags_stack_and_effects(self):
        for variant,sites in self.profiles.items():
            for site in sites.values():
                for flags in (0x202,0x242,0x282,0xa02,0xa82):
                    original=self.run_code(site,0,0,flags,False)
                    for scope,mode in ((0,0),(0,99),(0,1),(1,1),(1,2),(1,0xffffffff)):
                        with self.subTest(variant=variant,site=site['name'],scope=scope,mode=mode,flags=flags):
                            self.assertEqual(self.run_code(site,scope,mode,flags,True),original)

    def test_only_active_single_player_uses_replay_changes(self):
        for variant,sites in self.profiles.items():
            for site in sites.values():
                for mode in (0,99):
                    with self.subTest(variant=variant,site=site['name'],mode=mode):
                        result=self.run_code(site,1,mode,0x202,True)
                        self.assertEqual(result[-2],0) # suppressed calls never reach their callee
                        if site['patch']=='seed': self.assertEqual(result[-1],123)
                        if site['patch']=='taken': self.assertEqual(result[-3],site['target'])
                        if site['patch']=='cleanup': self.assertEqual(result[7],0x4108000+44)

    def test_multiplayer_tick_ignores_stale_halt_and_does_not_call_recorder(self):
        engines=self.lua.execute((ROOT/'code/engine-sites.lua').read_text())
        for variant,engine in engines.items():
            tick=engine['tick']; tick['patch']='tick'; tick['kind']='raw'
            tick['halt']=0x60010c; tick['callback']=0x4f0000; tick['skipTick']=tick['address']+0x25
            original=self.run_code(tick,0,0,0xa83,False)
            for enabled,mode in ((0,0),(0,99),(1,1),(1,2)):
                with self.subTest(variant=variant,enabled=enabled,mode=mode):
                    self.assertEqual(self.run_code(tick,enabled,mode,0xa83,True,halt=1),original)
            active=self.run_code(tick,1,0,0xa83,True,halt=0)
            self.assertEqual(active[:-2],original[:-2]); self.assertEqual(active[-2],1)
            stopped=self.run_code(tick,1,0,0xa83,True,halt=1)
            self.assertEqual(stopped[-3],tick['skipTick'])
            self.assertEqual(stopped[7],0x4108000); self.assertEqual(stopped[8],0xa83)

    def test_optional_tick_diagnostics_preserve_native_multiplayer_execution(self):
        engines=self.lua.execute((ROOT/'code/engine-sites.lua').read_text())
        for variant,engine in engines.items():
            tick=engine['tick']; tick['patch']='tick'; tick['kind']='raw'
            tick['halt']=0x60010c; tick['callback']=0x4f0000; tick['skipTick']=tick['address']+0x25
            tick['originalCallback']=0x4f0100
            for flags in (0x202,0x242,0xa83):
                original=self.run_code(tick,0,0,flags,False)
                for enabled,mode in ((0,0),(0,1),(1,1),(1,2)):
                    with self.subTest(variant=variant,flags=flags,scope=enabled,mode=mode):
                        observed=self.run_code(tick,enabled,mode,flags,True,halt=1)
                        self.assertEqual(observed[:-2],original[:-2])
                        self.assertEqual(observed[-1],original[-1])
                        self.assertEqual(observed[-2],1)
