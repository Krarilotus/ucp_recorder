"""Exercise the native DirectPlay receive-result/sender branch without transport."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_GRP_JUMP, CS_OP_IMM
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EBP,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EIP, UC_X86_REG_ESP)


def check_system_branch(reader,variant,site):
    start=site['address']-0x2e # immediately after native IDirectPlay4A::Receive
    code=reader(start,0x2e)
    decoder=Cs(CS_ARCH_X86,CS_MODE_32); decoder.detail=True
    instructions=list(decoder.disasm(code,start))
    assert instructions[-1].address+instructions[-1].size==site['address']
    exits={i.operands[0].imm for i in instructions
        if i.group(CS_GRP_JUMP) and i.operands[0].type==CS_OP_IMM}
    assert len(exits)==3 # no messages / unexpected result / ordinary sender
    base=0x191d768 if variant=='SHC' else 0x23547d8
    for result in (0,0x8000000a,0x887700be,0x80004005):
        for sender in (0,103):
            machine=Uc(UC_ARCH_X86,UC_MODE_32)
            machine.mem_map(0x400000,0x3e00000)
            machine.mem_write(start,code)
            machine.mem_write(base+0x69c,struct.pack('<I',sender))
            for register,value in ((UC_X86_REG_EAX,result),(UC_X86_REG_EBP,0),
                    (UC_X86_REG_ESI,base),(UC_X86_REG_EBX,base+0x69c),
                    (UC_X86_REG_EDI,base+0xcd8),(UC_X86_REG_ESP,0x4108000)):
                machine.reg_write(register,value)
            def stop(uc,address,size,data):
                if address in exits or address==site['address']: uc.emu_stop()
            machine.hook_add(UC_HOOK_CODE,stop)
            machine.emu_start(start,0,count=100)
            reached=machine.reg_read(UC_X86_REG_EIP)
            assert reached in exits or reached==site['address']
            assert (reached==site['address'])==(result==0 and sender==0)
            assert machine.reg_read(UC_X86_REG_ESP)==0x4108000
    print(f'PASS: {variant} 8 native receive-result/sender cases; system hook only sees successful sender-zero messages')
