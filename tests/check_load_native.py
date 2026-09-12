"""Original load failure exits and post-load identity reconstruction.

Allocation/file calls and menu/queue callees are stubs. This establishes hook
boundaries, not complete save decoding or live multiplayer restoration.
"""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP, UC_X86_REG_EIP)


def check_load(reader, lua, root, variant):
    sites=lua.execute((root/'code/engine-sites.lua').read_text())[variant]
    shift=0 if variant=='SHC' else 0x230
    begin=0x474a20+shift
    marker=sites.loadWorldComplete.address
    original=reader(begin,marker+15-begin)
    def target(offset):
        assert original[offset]==0xe8
        return begin+offset+5+struct.unpack_from('<i',original,offset+1)[0]
    malloc,filename,open_file,free=map(target,(0x18,0x4b,0x57,0x6d))
    stack,stop=0x4008000,0x4010000
    cases=0
    for failure in ('payload allocation','header allocation','file open'):
        m=Uc(UC_ARCH_X86,UC_MODE_32); m.mem_map(0x400000,0x4000000)
        m.mem_write(begin,original)
        def put(a,v): m.mem_write(a,struct.pack('<I',v&0xffffffff))
        def integer(a): return struct.unpack('<I',m.mem_read(a,4))[0]
        put(stack,stop); put(stack+4,sites.sections)
        m.reg_write(UC_X86_REG_ESP,stack); m.reg_write(UC_X86_REG_ECX,sites.packager)
        preserved={UC_X86_REG_EBX:17,UC_X86_REG_ESI:23,UC_X86_REG_EDI:29,UC_X86_REG_EBP:31}
        for reg,value in preserved.items(): m.reg_write(reg,value)
        markers=[]
        def observe(machine,address,size,unused):
            if address==marker: markers.append(address)
            if address not in (malloc,filename,open_file,free): return
            sp=machine.reg_read(UC_X86_REG_ESP)
            result=0
            if address==malloc:
                requested=integer(sp+4)
                assert requested in (6000000,100000)
                failed=(failure=='payload allocation' and requested==6000000
                    or failure=='header allocation' and requested==100000)
                result=0 if failed else (0x3000000 if requested==6000000 else 0x3700000)
            elif address==filename: result=0x3800000
            elif address==open_file: result=0xffffffff
            machine.reg_write(UC_X86_REG_EAX,result)
            machine.reg_write(UC_X86_REG_EIP,integer(sp)); machine.reg_write(UC_X86_REG_ESP,sp+4)
        m.hook_add(UC_HOOK_CODE,observe)
        m.emu_start(begin,stop,count=1000)
        assert m.reg_read(UC_X86_REG_EIP)==stop and not markers, (variant,failure)
        assert m.reg_read(UC_X86_REG_ESP)==stack+8
        assert all(m.reg_read(reg)==value for reg,value in preserved.items())
        cases+=1

    # The marker is a full, nonbranching store reached only on the completion
    # path. Its following epilogue also preserves the caller's saved registers.
    m=Uc(UC_ARCH_X86,UC_MODE_32); m.mem_map(0x400000,0x4000000)
    tail=reader(marker,15); assert tail[:2]==b'\x89\x1d' and tail[-3:]==b'\xc2\x04\x00'
    m.mem_write(marker,tail)
    received=struct.unpack_from('<I',tail,2)[0]
    m.mem_write(received,struct.pack('<I',123))
    m.mem_write(stack,struct.pack('<8I',31,23,17,0,0,0,stop,sites.sections))
    m.reg_write(UC_X86_REG_ESP,stack); m.reg_write(UC_X86_REG_EBX,0)
    m.emu_start(marker,stop,count=20)
    assert m.reg_read(UC_X86_REG_ESP)==stack+32
    assert bytes(m.mem_read(received,4))==bytes(4)
    assert [m.reg_read(r) for r in (UC_X86_REG_EBP,UC_X86_REG_ESI,UC_X86_REG_EBX)]==[31,23,17]
    cases+=1

    delta=0 if variant=='SHC' else 0x160
    start,end=0x495656+delta,sites.loadHandlerComplete.address
    base=0x191d768 if variant=='SHC' else 0x23547d8
    player=0x1a275dc if variant=='SHC' else 0x24baadc
    switch=0x46b340 if variant=='SHC' else 0x46b560
    # Native menu switching writes requestedView, not the currently drawn view.
    assert reader(switch+0x18,6)==bytes.fromhex('89 6e 18 89 46 04')
    queue=sites.queue.address
    game=sites.gameCore
    m=Uc(UC_ARCH_X86,UC_MODE_32); m.mem_map(0x400000,0x4000000)
    m.mem_write(start,reader(start,end-start))
    m.mem_write(switch,b'\xc2\x08\x00'); m.mem_write(queue,b'\xc2\x04\x00')
    def put(a,v): m.mem_write(a,struct.pack('<I',v&0xffffffff))
    def integer(a): return struct.unpack('<i',m.mem_read(a,4))[0]
    commands=[]; menus=[]
    def observe_tail(machine,address,size,unused):
        sp=machine.reg_read(UC_X86_REG_ESP)
        if address==queue: commands.append(integer(sp+4))
        if address==switch: menus.append(integer(sp+4)); put(game+0x18,integer(sp+4))
    m.hook_add(UC_HOOK_CODE,observe_tail)
    for mode in (0,99,1,2):
        for local in range(9):
            for icon in (0,1,2,7):
                commands.clear(); menus.clear()
                for i in range(9): put(base+0x6a8+i*4,100+i); put(base+0x714+i*4,3+i)
                put(game+12,41); put(game+0x18,41)
                put(base+0x618,mode); put(player,local); put(game+0x22e8,icon)
                m.reg_write(UC_X86_REG_EBX,0); m.reg_write(UC_X86_REG_EDI,0xffffffff)
                m.reg_write(UC_X86_REG_EBP,1); m.reg_write(UC_X86_REG_ESP,stack)
                m.emu_start(start,end,count=1000)
                assert m.reg_read(UC_X86_REG_EIP)==end
                assert integer(game+12)==41 and integer(game+0x18)==(14 if mode in (0,99) else 33)
                handles=[integer(base+0x6a8+i*4) for i in range(9)]
                if mode in (0,99):
                    expected=[-1]*9; expected[local or 1]=1
                    assert handles==expected and integer(player)==(local or 1) and menus==[14]
                    assert commands==([116] if mode==99 and icon>=2 else [])
                else:
                    assert handles==list(range(100,109)) and menus==[33] and not commands
                assert [integer(base+0x714+i*4) for i in range(9)]==list(range(3,12))
                cases+=1
    print(f'PASS: {variant} {cases} original load failure/completion/identity cases; OS and menu callees stubbed')
