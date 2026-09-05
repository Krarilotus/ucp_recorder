"""Original-binary regression for the heads-on-spikes command/preview tail.

Invoked by check_executables.py. Runs native code and native RNG in Unicorn,
stubbing only queueCommand so its payload is observable without a running game.
"""
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EFLAGS, UC_X86_REG_EIP)


def check_heads_placement(reader,lua,variant,sites):
    site=next(s for s in sites.values() if s['name']=='headsNextPreview')
    shc=variant=='SHC'
    start=0x445718 if shc else 0x445948
    preview=0x1fe7c24 if shc else 0x2a7b124
    player=0x1a275dc if shc else 0x24baadc
    synchrony=0x191d768 if shc else 0x23547d8
    payload=synchrony+0x7a850
    queue=0x489100 if shc else 0x489210
    rng=0x1a279c0 if shc else 0x24baec0
    emitter=lua.execute((Path(__file__).resolve().parents[1]/'code/scoped-code.lua').read_text())
    regs=(UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,
          UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP,UC_X86_REG_EFLAGS)

    def run(enabled,mode,current,gated):
        machine=Uc(UC_ARCH_X86,UC_MODE_32)
        machine.mem_map(0x400000,0x3e00000)
        def put(a,v): machine.mem_write(a,struct.pack('<I',v & 0xffffffff))
        def get(a): return struct.unpack('<I',machine.mem_read(a,4))[0]
        machine.mem_write(start,reader(start,site['address']+5-start))
        machine.mem_write(site['target'],reader(site['target'],0x29))
        machine.mem_write(queue,b'\xc2\x04\x00')
        put(0x600104,enabled); put(0x600108,mode)
        put(preview,5); put(player,3)
        machine.mem_write(rng,struct.pack('<h',current))
        machine.mem_write(rng+8+2*19999,struct.pack('<h',17))
        put(rng+0x9c4c,19999) # exercise native index wrap as well
        before=bytes(machine.mem_read(rng,0x9c50))
        # Callee-saved registers and local storage have already been pushed by
        # the original function; the tail must unwind them and return exactly once.
        for i,v in enumerate((0x1111,0x2222,0x3333,0x4444,0,0,0x4f1000)):
            put(0x4108000+4*i,v)
        for r,v in zip(regs,(0,0,0,0,123,4,456,0x4108000,0x202)):
            machine.reg_write(r,v)
        if gated:
            machine.mem_write(0x4000000,bytes(emitter.build(site,0x600104,0x600108,123,0x4000000).values()))
            machine.mem_write(site['address'],bytes(emitter.jump(site['address'],0x4000000,5).values()))
        commands=[]
        def observe(uc,address,size,data):
            if address==queue:
                assert uc.reg_read(UC_X86_REG_ECX)==synchrony
                commands.append((get(uc.reg_read(UC_X86_REG_ESP)+4),bytes(uc.mem_read(payload,24))))
            if address==0x4f1000: uc.emu_stop()
        machine.hook_add(UC_HOOK_CODE,observe)
        machine.emu_start(start,0,count=2000)
        assert machine.reg_read(UC_X86_REG_EIP)==0x4f1000
        assert commands==[(0x45,struct.pack('<6I',3,123,456,4,15,5))]
        # C signed remainder, including defensive negative input coverage.
        assert get(preview)==(current-int(current/7)*7)&0xffffffff
        assert [machine.reg_read(r) for r in (UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_EBX)]==[0x1111,0x2222,0x3333,0x4444]
        assert machine.reg_read(UC_X86_REG_ESP)==0x410801c
        after=bytes(machine.mem_read(rng,0x9c50))
        if gated and enabled and mode in (0,99): assert after==before
        else:
            assert get(rng+0x9c4c)==0
            assert struct.unpack('<h',after[:2])[0]==17
        return tuple(machine.reg_read(r) for r in regs),after,commands,get(preview)

    for current in (0,1,6,7,32767,-1,-32768):
        original=run(0,0,current,False)
        for enabled,mode in ((0,0),(0,99),(1,1),(1,2),(1,0xffffffff)):
            assert run(enabled,mode,current,True)==original
        for mode in (0,99): run(1,mode,current,True)
    print(f'PASS: {variant} 56 native heads-placement cases, command payload, preview, RNG and return stack')
