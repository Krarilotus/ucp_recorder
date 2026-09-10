"""Run the original save-time mode branch; synchronization callee is a stub."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ESI, UC_X86_REG_EIP


def check_save_pacing(reader,lua,root,variant):
    site=lua.execute((root/'code/offline-sites.lua').read_text())[variant].savePacing
    emitter=lua.execute((root/'code/scoped-code.lua').read_text())
    start=site.address; stop=start+0x27
    source=reader(start,0x27)
    assert source[:5]==bytes(site.bytes.values())
    assert source[0x22]==0xe8
    target=start+0x27+struct.unpack_from('<i',source,0x23)[0]
    machine=Uc(UC_ARCH_X86,UC_MODE_32); machine.mem_map(0x400000,0x4000000)
    flag,code,packager,stack=0x3c00000,0x3d00000,0x3e00000,0x4108000
    machine.mem_write(target,b'\xc3')
    gate=bytes(emitter.build(site,flag,None,None,code).values())
    machine.mem_write(code,gate)
    mode_address=struct.unpack_from('<I',source,1)[0]
    calls=[]
    machine.hook_add(UC_HOOK_CODE,lambda uc,ip,size,data:calls.append(ip) if ip==target else None)
    cases=0
    for patched in (False,True):
        for active in (0,1):
            for mode in (0,99,1,2):
                for section in (0,1,10,121):
                    calls.clear()
                    machine.mem_write(start,source)
                    if patched: machine.mem_write(start,bytes(emitter.jump(start,code,5).values()))
                    machine.ctl_remove_cache(start,stop)
                    machine.mem_write(flag,struct.pack('<I',active))
                    machine.mem_write(mode_address,struct.pack('<I',mode))
                    machine.mem_write(packager+12,struct.pack('<I',section))
                    machine.reg_write(UC_X86_REG_ESI,packager)
                    machine.reg_write(UC_X86_REG_ESP,stack)
                    machine.emu_start(start,stop,count=1000)
                    expected=mode not in (0,99) and section%10==0 and not (patched and active)
                    assert len(calls)==int(expected),(variant,patched,active,mode,section,calls)
                    assert machine.reg_read(UC_X86_REG_ESP)==stack
                    assert machine.reg_read(UC_X86_REG_ESI)==packager
                    assert struct.unpack('<I',machine.mem_read(mode_address,4))[0]==mode
                    cases+=1
    print(f'PASS: {variant} {cases} original save transport branches; offline suppresses call without changing mode')
