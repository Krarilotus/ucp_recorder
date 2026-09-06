"""Run original production serialization, command execution and UID-checked action."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from native_image import load_image


def check_production(path,variant):
    shc=variant=='SHC'
    base=0x191d768 if shc else 0x23547d8
    start=0x482290 if shc else 0x482460
    cursor=base+(0x109ee4 if shc else 0x166374)
    params=base+0x7a850
    actor=base+(0x109e70 if shc else 0x166300)
    uc=Uc(UC_ARCH_X86,UC_MODE_32);load_image(uc,path)
    def get(a):return struct.unpack('<I',uc.mem_read(a,4))[0]
    def put(a,v):uc.mem_write(a,struct.pack('<I',v&0xffffffff))
    decoder=Cs(CS_ARCH_X86,CS_MODE_32);decoder.detail=True
    instructions=list(decoder.disasm(bytes(uc.mem_read(start,0xd0)),start))
    action=[i.operands[0].imm for i in instructions if i.mnemonic=='call'][-1]
    native=list(decoder.disasm(bytes(uc.mem_read(action,0x23)),action))
    uid_base=next(i.operands[1].mem.disp for i in native if i.mnemonic=='mov' and i.op_str.startswith('ecx, dword ptr [eax'))
    produced_base=next(i.operands[0].mem.disp for i in native if i.mnemonic=='mov' and i.op_str.startswith('word ptr [eax'))
    stop=0x3df1000
    uc.hook_add(UC_HOOK_CODE,lambda u,a,s,d:u.emu_stop() if a==stop else None)
    def run(phase,slot):
        put(base+0x2d824,slot);put(base+0x2d828,phase);put(cursor,0);put(0x4108000,stop)
        initial={'ESP':0x4108000,'EBX':0x1111,'ESI':0x2222,'EDI':0x3333,'EBP':0x4444,'EFLAGS':0x202}
        for n,v in initial.items():uc.reg_write(getattr(reg,'UC_X86_REG_'+n),v)
        uc.emu_start(start,0,count=10000)
        assert uc.reg_read(reg.UC_X86_REG_EIP)==stop
        assert uc.reg_read(reg.UC_X86_REG_ESP)==0x4108004
        for n in ('EBX','ESI','EDI','EBP'):assert uc.reg_read(getattr(reg,'UC_X86_REG_'+n))==initial[n]
        assert get(cursor)==7 and get(base+0x2d830)==7
    count=0
    for slot in (0,199):
        for building in (1,17,1499):
            for product in (0,1,2,3,4,5,6,7,255):
                for uid in (1,0x12345678,0x80000001):
                    payload=struct.pack('<HBI',building,product,uid)
                    for i,v in enumerate((building,product,uid)):put(params+i*4,v)
                    run(1,slot)
                    address=base+0x3c686+1272*slot
                    assert bytes(uc.mem_read(address,7))==payload
                    for matches in (False,True):
                        put(uid_base+building*0x32c,uid if matches else uid^1)
                        uc.mem_write(produced_base+building*0x32c,struct.pack('<H',777))
                        for i in range(3):put(params+i*4,0xdeadbeef)
                        put(actor,1)
                        run(0,slot)
                        result=struct.unpack('<H',uc.mem_read(produced_base+building*0x32c,2))[0]
                        assert result==(product if matches else 777)
                        assert get(uid_base+building*0x32c)==(uid if matches else uid^1)
                        assert [get(params+i*4) for i in range(3)]==[building,product,uid]
                        count+=1
    print(f'PASS: {variant} {count} original production round trips and UID-checked state changes, no callee stand-ins')
