"""Original button dispatch: inert labels, current coordinates, hover and press."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP


def check_overlay_input(reader,lua,root,variant):
    sites=lua.execute((root/'tests/fixtures/ui-sites.lua').read_text())[variant]
    delta=0 if variant=='SHC' else 0x390
    item_handler=0x4f4290+delta
    machine=Uc(UC_ARCH_X86,UC_MODE_32); machine.mem_map(0x400000,0x3000000)
    machine.mem_write(item_handler,reader(item_handler,sites.updateMenu.address+38-item_handler))
    decode=Cs(CS_ARCH_X86,CS_MODE_32); decode.detail=True
    instructions=list(decode.disasm(reader(item_handler,400),item_handler))
    hitbox_call=next(i for i in instructions if i.mnemonic=='call' and i.op_str.startswith('0x'))
    hitbox=hitbox_call.operands[0].imm
    machine.mem_write(hitbox,reader(hitbox,57))
    clock_load=next(i for i in instructions if i.mnemonic=='mov' and i.op_str.startswith('ebp, dword ptr ['))
    menu,array,stack,stop,callback,clock=0x3100000,0x3101000,0x3300000,0x3301000,0x3302000,0x3303000
    def put(address,value): machine.mem_write(address,struct.pack('<I',value&0xffffffff))
    def get(address): return struct.unpack('<I',machine.mem_read(address,4))[0]
    put(clock_load.operands[1].mem.disp,clock)
    machine.mem_write(clock,b'\xb8\xe8\x03\0\0\xc3'); machine.mem_write(callback,b'\xc3')
    put(menu,array); put(menu+0x1c,-1000); put(menu+0x20,-1000) # tooltip anchors are unrelated
    for index,kind in enumerate((0,3)):
        item=array+index*80
        for offset,value in ((0,kind),(4,240),(8,12),(12,254),(16,18),(20,callback),(24,index),(36,1),(76,menu)):
            put(item+offset,value)
    put(array+160,0x66)
    seen=[]
    def called(uc,ip,size,context): seen.append(get(uc.reg_read(UC_X86_REG_ESP)+4))
    machine.hook_add(UC_HOOK_CODE,called,begin=callback,end=callback)
    mouse=sites.mouse.value
    for x,y,press in ((239,20,1),(240,12,1),(493,29,1),(494,20,1),(300,30,1),(300,20,0)):
        seen.clear(); put(mouse+0x10,x); put(mouse+0x14,y); put(mouse+0x34,press)
        put(mouse+0x40,press)
        machine.mem_write(stack,struct.pack('<I',stop))
        machine.reg_write(UC_X86_REG_ECX,menu); machine.reg_write(UC_X86_REG_ESP,stack)
        machine.emu_start(sites.updateMenu.address,stop,count=20000)
        inside=240<=x<494 and 12<=y<30
        assert seen==([0,1] if inside and press else [0]),(variant,x,y,press,seen)
        assert get(menu+0x38)==(array+80 if inside else 0)
        assert get(sites.menuHit.value)==int(inside)
        assert machine.reg_read(UC_X86_REG_ESP)==stack+4
    print(f'PASS: {variant} original menu update skips decorative hitboxes, reaches bar and resets hover; clock/callbacks stubbed',flush=True)
