"""Verify the result observer against native SKMasters insertion and rejection.

Only the already-tested packer and disk writer are substituted. Insertion,
ranking, shifting, capacity handling and EBX ownership execute original code.
"""
from pathlib import Path
import argparse
import struct
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EBX, UC_X86_REG_ESP
from native_image import load_image


def check(folder):
    root = Path(__file__).resolve().parents[1]
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().root = root.as_posix()
    lua.execute("package.path=root..'/?.lua;'..package.path")
    sites = lua.eval("require('code/match-results').sites")
    for variant, file, store, pack, writer, temporary, count_address in (
        ('SHC', 'Stronghold Crusader.exe', 0x4d52a0, 0x4d1700, 0x4d5180, 0xdf5658, 0xdf624c),
        ('Extreme', 'Stronghold_Crusader_Extreme.exe', 0x4d5630, 0x4d1950, 0x4d5520, 0xdf56f0, 0xdf62e4),
    ):
        site = sites[variant]
        for count, score, accepted in ((0, 200, True), (3, 200, True), (250, 200, True), (250, 0, False)):
            machine = Uc(UC_ARCH_X86, UC_MODE_32)
            load_image(machine, folder/file)
            assert bytes(machine.mem_read(site.address, len(site.bytes))) == bytes(site.bytes.values())
            assert bytes(machine.mem_read(site.address-7, 7)) == b'\xbe'+struct.pack('<I', temporary)+b'\xf3\xa5'
            assert bytes(machine.mem_read(store+5, 5)) == b'\xe8'+struct.pack('<i', pack-store-10)
            assert bytes(machine.mem_read(store+0xc3, 5)) == b'\xe9'+struct.pack('<i', writer-store-0xc8)
            machine.mem_map(0x5000000, 0x10000)
            stack, stop = 0x5009000, 0x5001000
            raw = bytearray(0xbf0)
            raw[4:8] = b'New\0'; struct.pack_into('<I', raw, 0x3ec, score)
            old = bytearray(0xbf0)
            old[4:8] = b'Old\0'; struct.pack_into('<I', old, 0x3ec, 100)
            machine.mem_write(temporary, bytes(raw))
            machine.mem_write(site.records, bytes(old)*250)
            machine.mem_write(count_address, struct.pack('<I', count))
            machine.mem_write(pack, b'\xb8\x01\x00\x00\x00\xc3')
            machine.mem_write(writer, b'\xc3')
            machine.mem_write(stack, struct.pack('<II', stop, 0))
            machine.reg_write(UC_X86_REG_ESP, stack)
            observed = []

            def at_insert(uc, address, size, data):
                index = uc.reg_read(UC_X86_REG_EBX)
                observed.append((index, bytes(uc.mem_read(site.records+index*0xbf0, 0xbf0))))

            machine.hook_add(UC_HOOK_CODE, at_insert, begin=site.address, end=site.address)
            machine.emu_start(store, stop, count=1000000)
            assert machine.reg_read(UC_X86_REG_ESP) == stack+4
            assert observed == ([(0, bytes(raw))] if accepted else [])
            new_count = struct.unpack('<I', machine.mem_read(count_address, 4))[0]
            assert new_count == (min(250, count+1) if accepted else count)
            if accepted and count:
                assert bytes(machine.mem_read(site.records+0xbf0, 0xbf0)) == bytes(old)
            if not accepted:
                assert bytes(machine.mem_read(site.records, 250*0xbf0)) == bytes(old)*250
        print(f'{variant}: native result insertion, full-history eviction and rejection passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    check(parser.parse_args().folder)
