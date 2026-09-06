"""Load original PE sections into an isolated x86 emulator, without Windows."""
import struct


def load_image(machine, path):
    data = path.read_bytes()
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    assert data[pe:pe+4] == b'PE\0\0'
    sections, optional_size = struct.unpack_from('<H', data, pe+6)[0], struct.unpack_from('<H', data, pe+20)[0]
    base = struct.unpack_from('<I', data, pe+24+28)[0]
    assert base == 0x400000
    machine.mem_map(base, 0x3e00000)
    headers = pe+24+optional_size
    for i in range(sections):
        _, address, size, offset = struct.unpack_from('<IIII', data, headers+i*40+8)
        assert base+address+size <= 0x4200000 and offset+size <= len(data)
        if size:
            machine.mem_write(base+address, data[offset:offset+size])
