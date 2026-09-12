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
    def test_relocated_return_address_mapping_matches_emitted_call(self):
        for profile in self.profiles.values():
            for site in profile.values():
                if site['kind'] != 'call':
                    continue
                mapping = self.lua.table()
                origin = 0x4000000
                encoded = bytes(self.emitter.build(site, 0x600104, 0x600108, 123, origin, mapping).values())
                self.assertEqual(len(list(mapping.items())), 1)
                for relocated, original in mapping.items():
                    offset = relocated-origin-5
                    self.assertEqual(encoded[offset], 0xe8)
                    self.assertEqual(relocated+struct.unpack_from('<i', encoded, offset+1)[0], site['target'])
                    self.assertEqual(original, site['address']+len(site['bytes']))

    def setUp(self):
        self.lua=LuaRuntime()
        self.emitter=self.lua.execute((ROOT/'code/scoped-code.lua').read_text())
        self.profiles=self.lua.execute((ROOT/'code/scoped-sites.lua').read_text())

    def run_code(self,site,enabled,mode,flags,gated,halt=0,offline=None,local_gate=False,
                 viewing=0,paused=0,modal=0):
        machine=Uc(UC_ARCH_X86,UC_MODE_32)
        machine.mem_map(0x400000,0x3000000)
        machine.mem_map(0x4000000,0x1000)
        machine.mem_map(0x4100000,0x10000)
        original=bytes(site['bytes'].values())
        machine.mem_write(site['address'],original)
        counter,scope,mode_pointer=0x600100,0x600104,0x600108
        def put(address,value): machine.mem_write(address,struct.pack('<I',value&0xffffffff))
        put(scope,enabled); put(mode_pointer,mode)
        put(0x600110,offline or 0)
        if site['patch']=='tickEntry':
            put(site['halt'],halt); put(site['playback'],viewing); put(site['paused'],paused)
            # A thiscall callee may destroy all volatile registers. The entry
            # gate must restore the original receiver, flags and argument stack.
            machine.mem_write(site['menu'],b'\xb8'+struct.pack('<I',modal)
                +b'\xb9\x22\0\0\0\xba\x33\0\0\0\xc3')
        if site['patch']=='tick':
            put(site['halt'],halt)
            machine.mem_write(site['callback'],b'\xff\x05'+struct.pack('<I',counter)+b'\xb8\x01\0\0\0\xc3')
            if site['originalCallback']:
                machine.mem_write(site['originalCallback'],b'\xff\x05'+struct.pack('<I',counter)
                    + b'\xb8\x11\0\0\0\xb9\x22\0\0\0\xba\x33\0\0\0\xc3')
        if gated:
            gate=bytes(self.emitter.build(site,scope,None if local_gate else mode_pointer,123,
                0x4000000,None,0x600110 if offline is not None else None).values())
            machine.mem_write(0x4000000,gate)
            machine.mem_write(site['address'],bytes(self.emitter.jump(site['address'],0x4000000,len(original)).values()))
        if site['kind'] in ('call','tail'):
            ret=b'\xc2\x2c\0' if site['patch']=='cleanup' else b'\xc3'
            machine.mem_write(site['target'],b'\xff\x05'+struct.pack('<I',counter)+b'\xb8\x01\0\0\0'+ret)
        initial=[0x500000,0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000,0x4108000,flags]
        for register,value in zip(REGS,initial): machine.reg_write(register,value)
        stops={site['address']+len(original)}
        if site['kind']=='tail' or site['patch'] in ('return','tickEntry'):
            put(initial[7],0x4f1000)
            stops.add(0x4f1000)
        if site['kind']=='branch': stops.add(site['target'])
        if site['patch']=='tick': stops.add(site['skipTick'])
        def stop(uc,address,size,data):
            if address in stops: uc.emu_stop()
        machine.hook_add(UC_HOOK_CODE,stop)
        machine.emu_start(site['address'],0,count=1000)
        self.assertIn(machine.reg_read(UC_X86_REG_EIP),stops)
        return tuple(machine.reg_read(r) for r in REGS)+(machine.reg_read(UC_X86_REG_EIP),
            struct.unpack('<I',machine.mem_read(counter,4))[0],struct.unpack('<I',machine.mem_read(0x600004,4))[0])

    def test_viewer_pause_admission_preserves_original_thiscall_contract(self):
        self.lua.globals().source_root=ROOT.as_posix()
        self.lua.execute("package.path=source_root..'/?.lua;'..package.path")
        fixes=self.lua.eval("require('code/fixes')")
        engines=self.lua.execute((ROOT/'tests/fixtures/engine-sites.lua').read_text())
        for engine in engines.values():
            site=fixes.tickEntry(engine,0x60010c,0x600114)
            for flags in (0x202,0xa83):
                original=self.run_code(site,0,99,flags,False)
                for enabled,mode,offline in ((0,99,0),(0,1,1),(1,1,0),(1,2,0),(1,99,0),(1,1,1)):
                    for viewing,paused,modal,halt in ((0,1,1,0),(1,0,0,0),(1,1,0,0),
                                                       (1,0,1,0),(1,0,0,1)):
                        with self.subTest(mode=mode,offline=offline,flags=flags,viewing=viewing,
                                          paused=paused,modal=modal,halt=halt,enabled=enabled):
                            result=self.run_code(site,enabled,mode,flags,True,halt=halt,offline=offline,
                                                 viewing=viewing,paused=paused,modal=modal)
                            stop=enabled and (mode==99 or offline) and (halt or (viewing and (paused or modal)))
                            if stop:
                                self.assertEqual(result[:7],(0x500000,0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000))
                                self.assertEqual(result[7:10],(0x4108004,flags,0x4f1000))
                            else:
                                self.assertEqual(result,original)

    def test_offline_boundaries_preserve_live_code_and_callee_stack_contracts(self):
        profiles=self.lua.execute((ROOT/'tests/fixtures/offline-sites.lua').read_text())
        for variant,sites in profiles.items():
            for name,site in sites.items():
                for flags in (0x202,0xa83):
                    with self.subTest(variant=variant,site=name,flags=flags):
                        original=self.run_code(site,0,2,flags,False)
                        self.assertEqual(self.run_code(site,0,2,flags,True,local_gate=True),original)
                        active=self.run_code(site,1,2,flags,True,local_gate=True)
                        self.assertEqual(active[1:7],(0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000))
                        self.assertEqual(active[8],flags)
                        if site['patch']=='return':
                            self.assertEqual(active[7],0x4108004+(site['pop'] or 0))
                            self.assertEqual(active[-3],0x4f1000)
                        else:
                            self.assertEqual(active[0],99)
                            self.assertEqual(active[7],0x4108000)

    def test_offline_tick_can_halt_without_enabling_single_player_rng_fixes(self):
        engines=self.lua.execute((ROOT/'tests/fixtures/engine-sites.lua').read_text())
        for engine in engines.values():
            tick=engine['tick']; tick['patch']='tick'; tick['kind']='raw'
            tick['halt']=0x60010c; tick['callback']=0x4f0000; tick['skipTick']=engine['tickExit']['address']
            original=self.run_code(tick,0,2,0xa83,False)
            self.assertEqual(self.run_code(tick,0,2,0xa83,True,halt=1,offline=1),original)
            self.assertEqual(self.run_code(tick,1,2,0xa83,True,halt=1,offline=0),original)
            halted=self.run_code(tick,1,2,0xa83,True,halt=1,offline=1)
            self.assertEqual(halted[-3],tick['skipTick'])
            self.assertEqual(halted[-2],1)
            self.assertEqual(halted[7:9],(0x4108000,0xa83))

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
                        if site['patch']=='return':
                            self.assertEqual(result[-3],0x4f1000)
                            self.assertEqual(result[7],0x4108004)
                            self.assertEqual(result[:7],(0x500000,0x600010,0x600000,0x20,0x600000,0xabcdef00,0x410f000))
                            self.assertEqual(result[8],0x202)

    def test_multiplayer_tick_ignores_stale_halt_and_does_not_call_recorder(self):
        engines=self.lua.execute((ROOT/'tests/fixtures/engine-sites.lua').read_text())
        for variant,engine in engines.items():
            tick=engine['tick']; tick['patch']='tick'; tick['kind']='raw'
            tick['halt']=0x60010c; tick['callback']=0x4f0000; tick['skipTick']=engine['tickExit']['address']
            original=self.run_code(tick,0,0,0xa83,False)
            for enabled,mode in ((0,0),(0,99),(1,1),(1,2)):
                with self.subTest(variant=variant,enabled=enabled,mode=mode):
                    self.assertEqual(self.run_code(tick,enabled,mode,0xa83,True,halt=1),original)
            active=self.run_code(tick,1,0,0xa83,True,halt=0)
            self.assertEqual(active[:-2],original[:-2]); self.assertEqual(active[-2],1)
            stopped=self.run_code(tick,1,0,0xa83,True,halt=1)
            self.assertEqual(stopped[-3],tick['skipTick'])
            self.assertEqual(stopped[7],0x4108000); self.assertEqual(stopped[8],0xa83)

    def test_pause_gate_preserves_incoming_unpaused_branch(self):
        for variant,sites in self.profiles.items():
            site=next(s for s in sites.values() if s['patch']=='equalFlags')
            address=site['address']
            mode_pointer=struct.unpack('<I',bytes(site['bytes'].values())[2:6])[0]
            for enabled,mode in ((0,0),(1,0),(1,99),(1,1)):
                for paused in (0,1):
                    with self.subTest(variant=variant,enabled=enabled,mode=mode,paused=paused):
                        machine=Uc(UC_ARCH_X86,UC_MODE_32)
                        machine.mem_map(0x400000,0x4000000)
                        def put(a,v): machine.mem_write(a,struct.pack('<I',v))
                        put(0x600104,enabled); put(mode_pointer,mode); put(0x600108,paused)
                        # Original JE arrives at the MOV immediately after JGE.
                        machine.mem_write(address-9,b'\x83\x3d'+struct.pack('<I',0x600108)+b'\x00\x74\x09')
                        gate=bytes(self.emitter.build(site,0x600104,mode_pointer,123,0x4000000).values())
                        machine.mem_write(0x4000000,gate)
                        machine.mem_write(address,bytes(self.emitter.jump(address,0x4000000,7).values()))
                        machine.mem_write(address+7,b'\x7d\x46\xb9\x78\x56\x34\x12')
                        stops={address+14,address+0x4f}
                        def stop(uc,a,size,data):
                            if a in stops: uc.emu_stop()
                        machine.hook_add(UC_HOOK_CODE,stop)
                        machine.reg_write(UC_X86_REG_ESP,0x4108000)
                        machine.emu_start(address-9,0,count=1000)
                        skip=paused and (mode>=8 or (enabled and mode in (0,99)))
                        self.assertEqual(machine.reg_read(UC_X86_REG_EIP),address+0x4f if skip else address+14)
                        if not skip: self.assertEqual(machine.reg_read(UC_X86_REG_ECX),0x12345678)

    def test_optional_tick_diagnostics_preserve_native_multiplayer_execution(self):
        engines=self.lua.execute((ROOT/'tests/fixtures/engine-sites.lua').read_text())
        for variant,engine in engines.items():
            tick=engine['tick']; tick['patch']='tick'; tick['kind']='raw'
            tick['halt']=0x60010c; tick['callback']=0x4f0000; tick['skipTick']=engine['tickExit']['address']
            tick['originalCallback']=0x4f0100
            for flags in (0x202,0x242,0xa83):
                original=self.run_code(tick,0,0,flags,False)
                for enabled,mode in ((0,0),(0,1),(1,1),(1,2)):
                    with self.subTest(variant=variant,flags=flags,scope=enabled,mode=mode):
                        observed=self.run_code(tick,enabled,mode,flags,True,halt=1)
                        self.assertEqual(observed[:-2],original[:-2])
                        self.assertEqual(observed[-1],original[-1])
                        self.assertEqual(observed[-2],1)
