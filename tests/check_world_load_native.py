"""Run the original FilePackager reader on a generated native container.

The file/heap/clock APIs, resource names and audio notifications are simulated.
Directory parsing, world initialization, section routing, decompression and
post-load fixups execute original instructions. This does not exercise the outer
UI load handler, map-extensions wrappers, transport or a running match.
"""
from pathlib import Path
import json
import struct

from unicorn import UC_HOOK_CODE
from unicorn import x86_const as reg
from test_world_header import PARTS


def check_world_load(machine, folder: Path, variant: str, call, imports: dict):
    extreme = variant == 'Extreme'
    addresses = dict(zip(
        ('load', 'malloc', 'free', 'filename', 'open', 'read', 'close',
         'resource_name', 'map_name', 'sound_time', 'sound_load'),
        (0x474c50, 0x580481, 0x57fec1, 0x46c520, 0x581b10, 0x581a13, 0x581385,
         0x471f50, 0x46d5b0, 0x47a470, 0x47a300) if extreme else
        (0x474a20, 0x580034, 0x57fa74, 0x46c300, 0x5816c3, 0x5815c6, 0x580f38,
         0x471d30, 0x46d390, 0x47a2a0, 0x47a130)))
    packager = 0xf2b850 if extreme else 0xf2b3d0
    sections = 0xb92be8 if extreme else 0xb92a58
    container = (folder / 'world-native.sav').read_bytes()
    manifest = json.loads((folder / 'world.json').read_text())
    raw = (folder / 'world.bin').read_bytes()
    header = (folder / 'world-header.bin').read_bytes()
    cursor, heap_cursor = 0, 0x9000000
    allocations, restored, handles = {}, [], []
    opened = closed = False
    clock = 0x3df1100
    filename = 0x3df1200
    machine.mem_map(0x9000000, 0x1000000)
    machine.mem_write(filename, b'recorder-native-test.sav\0')

    def get(address):
        return struct.unpack('<I', machine.mem_read(address, 4))[0]

    def put(address, value):
        machine.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def verify_sections():
        for entry in manifest['sections']:
            expected = raw[entry['offset']:entry['offset'] + entry['size']]
            actual = bytes(machine.mem_read(entry['address'], entry['size']))
            assert actual == expected, (variant, 'native load section differs', entry['section'],
                next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), None))
            restored.append(entry['section'])
        offset = 0
        for _, parts in PARTS:
            for length, shc, shce, reference in parts:
                expected = header[offset:offset + length]
                # The native loader intentionally discards the saved string-
                # table flag, then optionally resolves an official map name.
                if offset == 0:
                    expected = bytes(4)
                address = shce if extreme else shc
                assert bytes(machine.mem_read(address, length)) == expected, (
                    variant, 'native header field differs', hex(address))
                offset += length
        assert offset == len(header)

    def api(uc, ip, size, unused):
        nonlocal cursor, heap_cursor, opened, closed
        sp = uc.reg_read(reg.UC_X86_REG_ESP)
        argument = lambda index: get(sp + index * 4)
        name = names[ip]
        result = 0
        if name == 'malloc':
            length = argument(1)
            assert length in (6000000, 100000)
            result = heap_cursor
            heap_cursor += length + 32
            allocations[result] = length
            uc.mem_write(result, bytes(length) + b'\xa5' * 32)
        elif name == 'free':
            pointer = argument(1)
            length = allocations.pop(pointer)
            assert bytes(uc.mem_read(pointer + length, 32)) == b'\xa5' * 32
            if length == 6000000:
                verify_sections()
        elif name in ('filename', 'resource_name'):
            result = filename
        elif name == 'map_name':
            put(argument(2), 0)
        elif name == 'open':
            assert not opened and argument(1) == filename and argument(2) == 0x8000
            opened, result = True, 17
        elif name == 'read':
            fd, destination, length = argument(1), argument(2), argument(3)
            assert opened and not closed and fd == 17 and cursor + length <= len(container)
            uc.mem_write(destination, container[cursor:cursor + length])
            cursor += length
            result = length
        elif name == 'close':
            assert argument(1) == 17 and cursor == len(container) and not closed
            closed = True
        elif name == 'clock':
            result = 123456
        else:
            assert name in ('sound_time', 'sound_load')
        # All simulated calls are cdecl or thiscall without stack arguments.
        uc.reg_write(reg.UC_X86_REG_EAX, result)
        uc.reg_write(reg.UC_X86_REG_EIP, get(sp))
        uc.reg_write(reg.UC_X86_REG_ESP, sp + 4)

    names = {address: name for name, address in addresses.items() if name != 'load'}
    names[clock] = 'clock'
    old_clock = get(imports['timeGetTime'])
    put(imports['timeGetTime'], clock)
    try:
        for address in names:
            handles.append(machine.hook_add(UC_HOOK_CODE, api, begin=address, end=address))
        # Poison each destination so a skipped read cannot pass with BSS zeros.
        for entry in manifest['sections']:
            machine.mem_write(entry['address'], b'\xcd' * entry['size'])
        for _, parts in PARTS:
            for length, shc, shce, reference in parts:
                machine.mem_write(shce if extreme else shc, b'\xcd' * length)
        put(packager + 0x20, 0)  # No rendering callback in the headless fixture.
        call(addresses['load'], sections, this=packager)
        assert opened and closed and not allocations and len(restored) == 122
    finally:
        for handle in handles:
            machine.hook_del(handle)
        put(imports['timeGetTime'], old_clock)
        machine.mem_unmap(0x9000000, 0x1000000)
    print(f'PASS: {variant} original FilePackager restores all 122 poisoned section destinations; '
          'file, heap, clock, resource names and audio APIs simulated', flush=True)
