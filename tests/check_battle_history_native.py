"""Original-executable checks: statistics packing is read-only outside its output.

Runs the actual packer, score and date-copy instructions in isolated x86 memory.
Only Windows GetLocalTime is substituted. No game installation is modified.
"""
from pathlib import Path
import argparse
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from capstone.x86 import X86_OP_IMM, X86_OP_MEM
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EIP
from native_image import load_image
from check_executables import image_reader


def check(folder,binding=None,pack_binding=None,variant_filter=None):
    root = Path(__file__).resolve().parents[1]
    decoder = Cs(CS_ARCH_X86, CS_MODE_32); decoder.detail = True
    for variant, filename, pack in (
        ('SHC', 'Stronghold Crusader.exe', 0x4d1700),
        ('Extreme', 'Stronghold_Crusader_Extreme.exe', 0x4d1950),
    ):
        if variant_filter and variant!=variant_filter:continue
        if pack_binding is not None:pack=pack_binding
        path = folder/filename; reader = image_reader(path)
        lua = LuaRuntime(unpack_returned_tuples=True)
        sites = binding or lua.execute((root/'tests/fixtures/history-sites.lua').read_text())[variant]
        expected = set()
        for site in sites.operands.values():
            assert reader(site.address, len(site.bytes)) == bytes(site.bytes.values())
            expected.add(site.address)
        found = set()
        for start, size in ((sites.frame.address, 0xeb3), (sites.action.address, 0x2c0)):
            for instruction in decoder.disasm(reader(start, size), start):
                values = [o.imm if o.type == X86_OP_IMM else o.mem.disp
                          for o in instruction.operands if o.type in (X86_OP_IMM, X86_OP_MEM)]
                if any(sites.records <= v < sites.records+0xbf0 or v == sites.index for v in values):
                    found.add(instruction.address)
        assert found == expected, (variant, 'uncovered native history data reference', found ^ expected)
        # Preparation saves the previous game mode here. Returning from a
        # results screen must preserve the original lobby value at this site.
        for key in ('prepareList','prepare','action','frame','helpText'):
            site=sites[key]
            assert reader(site.address,len(site.bytes))==bytes(site.bytes.values())
        assert reader(sites.prepareList.address+0x2a, 1) == b'\xa3'
        assert struct.unpack('<I',reader(sites.prepareList.address+0x2b,4))[0]==sites.savedMode
        # UCP copies these instructions to a different address verbatim. A
        # relative branch/call here would jump into unrelated heap memory.
        for key in ('prepare','action'):
            site=sites[key]
            ins=list(decoder.disasm(reader(site.address,len(site.bytes)),site.address))
            assert sum(i.size for i in ins)==len(site.bytes)
            assert not any(i.mnemonic.startswith(('j','call','loop')) for i in ins)
        temporary = struct.unpack('<I', reader(pack+5, 4))[0]
        instructions = []
        for instruction in decoder.disasm(reader(pack, 0x300), pack):
            instructions.append(instruction)
            if instruction.mnemonic == 'ret': break
        calls = [i for i in instructions if i.mnemonic == 'call']
        assert len(calls) == 2 and calls[0].address == pack+0x2a
        local_time = calls[1].operands[0].imm
        assert reader(local_time+7, 2) == b'\xff\x15'
        time_import = struct.unpack('<I', reader(local_time+9, 4))[0]
        machine = Uc(UC_ARCH_X86, UC_MODE_32); load_image(machine, path)
        machine.mem_map(0x5000000, 0x10000)
        stack, stop, clock = 0x5009000, 0x5001000, 0x5002000
        machine.mem_write(time_import, struct.pack('<I', clock))
        machine.mem_write(clock, b'\xc2\x04\x00')
        machine.mem_write(stack, struct.pack('<II', stop, 0))
        machine.reg_write(UC_X86_REG_ESP, stack)
        violations = []
        def writes(uc, access, address, size, value, data):
            if not (temporary <= address and address+size <= temporary+0xbf0
                    or stack-0x1000 <= address and address+size <= stack+8):
                violations.append((address, size))
        def windows_time(uc, address, size, data):
            if address == clock:
                pointer = struct.unpack('<I', uc.mem_read(uc.reg_read(UC_X86_REG_ESP)+4,4))[0]
                uc.mem_write(pointer, struct.pack('<8H',2026,9,3,9,12,30,0,0))
        machine.hook_add(UC_HOOK_MEM_WRITE, writes)
        machine.hook_add(UC_HOOK_CODE, windows_time)
        machine.emu_start(pack, stop, count=50000)
        assert machine.reg_read(UC_X86_REG_EIP) == stop
        assert machine.reg_read(UC_X86_REG_ESP) == stack+4
        assert not violations, (variant, violations)
        assert struct.unpack('<III',machine.mem_read(temporary+0x464,12)) == (9,9,2026)
        print(f'PASS: {variant} native statistics writes confined to temporary entry/stack; all history operands covered')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game', type=Path)
    check(parser.parse_args().game)
