"""Original mission-bar asset binding and clipping ABI; no raster emulation."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EBX


def check_mission_bar(reader,lua,root,variant):
    sites=lua.execute((root/'tests/fixtures/ui-sites.lua').read_text())[variant]
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
    decoder=Cs(CS_ARCH_X86,CS_MODE_32); decoder.detail=True
    calls=[i for i in decoder.disasm(reader(sites.clippedSprite.address,145),sites.clippedSprite.address) if i.mnemonic=='call']
    primitive=calls[0].operands[0].imm
    raster=list(decoder.disasm(reader(primitive,590),primitive))
    at={i.address:i for i in raster}
    map_pointer=at[primitive+0x37].operands[1].mem.disp
    screen_pointer=at[primitive+0x59].operands[1].mem.disp
    screen_stride=at[primitive+0x6d].operands[1].mem.disp
    machine.mem_write(primitive,reader(primitive,590))
    machine.mem_map(0x4000000,0x2000000)
    screen,map_surface,source=0x4000000,0x5000000,0x3302000
    def put(address,value): machine.mem_write(address,struct.pack('<I',value))
    put(screen_pointer,screen); put(map_pointer,map_surface); put(screen_stride,1600)
    # A synthetic opaque TGX strip drives the original rasterizer, not a draw stub.
    row=(b'\x5f\xe0\x07'*7)+b'\x59\xe0\x07\x80'
    machine.mem_write(source,row*12)
    for surface,x,y in ((0,22,32),(1,2022,1032)):
        put(texture+4,1-surface); put(texture+8,surface)
        machine.mem_write(texture+0x16c854,struct.pack('<4I',x,y,x+125,y+12))
        machine.mem_write(stack,struct.pack('<6I',stop,x,y,250,12,source))
        machine.reg_write(UC_X86_REG_ECX,texture); machine.reg_write(UC_X86_REG_ESP,stack)
        machine.emu_start(primitive,stop,count=100000)
        assert machine.reg_read(UC_X86_REG_ESP)==stack+24
        base,stride=(screen,1600) if surface==0 else (map_surface,0x1fb0)
        for line in range(12):
            assert machine.mem_read(base+(y+line)*stride+x*2,500)==b'\xe0\x07'*125+b'\0'*250
        other,other_stride=(map_surface,0x1fb0) if surface==0 else (screen,1600)
        assert machine.mem_read(other+y*other_stride+x*2,500)==b'\0'*500
    print(f'PASS: {variant} original mission strip binding, clip ABI and TGX pixels on independent screen/map targets',flush=True)
