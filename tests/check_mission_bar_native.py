"""Original mission-bar asset binding and clipping ABI; no raster emulation."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EBX


def check_mission_bar(reader,lua,root,variant):
    sites=lua.execute((root/'code/ui-sites.lua').read_text())[variant]
    reference=reader(sites.missionBar.address,17)
    assert reference[:8]==bytes.fromhex('6a0468a4000000b9')
    assert struct.unpack_from('<I',reference,8)[0]==sites.missionBar.value
    assert sites.missionBar.address+17+struct.unpack_from('<i',reference,13)[0]==sites.clippedSprite.address
    machine=Uc(UC_ARCH_X86,UC_MODE_32); machine.mem_map(0x400000,0x3000000)
    start=sites.spriteClip.address; texture=sites.missionBar.value
    machine.mem_write(start,reader(start,64))
    stack,stop=0x3300000,0x3301000
    for bounds in ((22,32,147,44),(2022,1032,2272,1044)):
        machine.reg_write(UC_X86_REG_ECX,texture); machine.reg_write(UC_X86_REG_ESP,stack)
        machine.reg_write(UC_X86_REG_EBX,123)
        machine.mem_write(stack,struct.pack('<5I',stop,*bounds))
        machine.emu_start(start,stop,count=100)
        assert machine.reg_read(UC_X86_REG_ESP)==stack+20 and machine.reg_read(UC_X86_REG_EBX)==123
        assert struct.unpack('<4I',machine.mem_read(texture+0x16c854,16))==bounds
    print(f'PASS: {variant} original green mission strip binding and clip ABI at screen/map coordinates; raster not simulated',flush=True)
