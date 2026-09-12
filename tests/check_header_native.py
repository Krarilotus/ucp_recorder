"""Exercise native banner tiling and ABI; texture blitting is a stand-in."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP


def check_header(reader, lua, root, variant):
    sites = lua.execute((root/'tests/fixtures/ui-sites.lua').read_text())[variant]
    start = sites.header.address
    instructions = []
    for item in Cs(CS_ARCH_X86, CS_MODE_32).disasm(reader(start, 0x200), start):
        instructions.append(item)
        if item.mnemonic == 'ret': break
    assert instructions[-1].mnemonic == 'ret' and instructions[-1].op_str == '0x10'
    targets = {int(i.op_str, 16) for i in instructions if i.mnemonic == 'call'}
    assert len(targets) == 1, 'Unexpected non-render dependency in native banner'
    draw = targets.pop()
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    machine.mem_write(start, reader(start, instructions[-1].address+instructions[-1].size-start))
    machine.mem_write(draw, b'\xc2\x1c\x00')
    stack, stop = 0x4000000, 0x4100000
    def read32(address): return struct.unpack('<I', machine.mem_read(address, 4))[0]
    drawn = []
    def observe(uc, address, size, data):
        if address == draw:
            sp = uc.reg_read(UC_X86_REG_ESP)
            drawn.append(tuple(read32(sp+4+i*4) for i in range(7)))
    machine.hook_add(UC_HOOK_CODE, observe)
    preserved = {UC_X86_REG_EBX: 11, UC_X86_REG_ESI: 12, UC_X86_REG_EDI: 13, UC_X86_REG_EBP: 14}
    for width in (600, 680):
        drawn.clear()
        for reg, value in preserved.items(): machine.reg_write(reg, value)
        machine.reg_write(UC_X86_REG_ESP, stack)
        machine.mem_write(stack, struct.pack('<5I', stop, 40, 50, width, 0))
        machine.emu_start(start, stop, count=20000)
        assert machine.reg_read(UC_X86_REG_ESP) == stack+20
        assert all(machine.reg_read(reg) == value for reg, value in preserved.items())
        tiles = (width-16)//8
        assert len(drawn) == tiles*8+2
        for row in range(8):
            band = drawn[row*tiles:(row+1)*tiles]
            assert [b[2] for b in band] == list(range(48, 40+width-8, 8))
            assert all(b[3] == 58+row*8 and b[0] == b[4] == 0x9c and b[5] == b[1]+3 for b in band)
        assert all(b[1] == 0x5b and b[5] == 0x5c for b in drawn[-2:])
    print(f'PASS: {variant} native header at both dialog widths; tile layout and callee ABI; texture blitting is stubbed')
