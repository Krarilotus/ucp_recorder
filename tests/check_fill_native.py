"""Check original Pencil fill ABI/row traversal; clip setup and raster are stubs."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EAX, UC_X86_REG_ESI


def check_fill(reader, lua, root, variant):
    sites = lua.execute((root/'code/ui-sites.lua').read_text())[variant]
    start = sites.fill.address
    instructions = []
    for instruction in Cs(CS_ARCH_X86, CS_MODE_32).disasm(reader(start, 0x80), start):
        instructions.append(instruction)
        if instruction.mnemonic == 'ret':
            break
    assert instructions[-1].op_str == '0x14'
    setup, clip, raster = [int(i.op_str, 16) for i in instructions if i.mnemonic == 'call']
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    machine.mem_write(start, reader(start, instructions[-1].address+instructions[-1].size-start))
    machine.mem_write(setup, b'\xc3')
    machine.mem_write(clip, b'\xc2\x14\x00')
    machine.mem_write(raster, b'\xc3')
    stack, stop, pencil = 0x4000000, 0x4100000, sites.pencil.value
    def read32(address):
        return struct.unpack('<I', machine.mem_read(address, 4))[0]
    rows = []
    clipped = False
    arguments = (20, 30, 115, 39, 0xffff)
    def observe(uc, address, size, data):
        if address in (setup, clip, raster):
            assert uc.reg_read(UC_X86_REG_ECX) == pencil
        if address == clip:
            sp = uc.reg_read(UC_X86_REG_ESP)
            assert tuple(read32(sp+4+i*4) for i in range(5)) == arguments
            uc.reg_write(UC_X86_REG_EAX, 0 if clipped else 1)
            uc.mem_write(pencil+0x2c, struct.pack('<I', 9))
            uc.mem_write(pencil+0x34, struct.pack('<I', 30))
        elif address == raster:
            rows.append(read32(pencil+0x34))
    machine.hook_add(UC_HOOK_CODE, observe)
    for clipped in (False, True):
        rows.clear()
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.reg_write(UC_X86_REG_ECX, pencil)
        machine.reg_write(UC_X86_REG_ESI, 123)
        machine.mem_write(stack, struct.pack('<6I', stop, *arguments))
        machine.emu_start(start, stop, count=1000)
        assert machine.reg_read(UC_X86_REG_ESP) == stack+24
        assert machine.reg_read(UC_X86_REG_ESI) == 123
        assert rows == ([] if clipped else list(range(30, 40)))
    print(f'PASS: {variant} native fill ABI, inclusive row traversal and clipped rejection; clipping/raster stubs')
