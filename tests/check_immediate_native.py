"""Run original local/remote immediate paths with the actual Lua payload reader.

Transport, allocation-free memory helpers and a synthetic command handler are
stand-ins. Queueing, native address selection, identity resolution and execution
branches are original SHC/Extreme instructions. No live process is accessed.
"""
from pathlib import Path
import struct
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg


def check_immediate(reader, variant):
    shc = variant == 'SHC'
    base = 0x191d768 if shc else 0x23547d8
    actor = 0x109e70 if shc else 0x166300
    write_index = 0x109ee0 if shc else 0x166370
    schedule = 0x480210 if shc else 0x4803e0
    queue = 0x489100 if shc else 0x489210
    translate = 0x47eaf0 if shc else 0x47ecc0
    copy = 0x471830 if shc else 0x471a50
    fill = 0x4718c0 if shc else 0x471ae0
    clear = 0x4800b0 if shc else 0x480280
    transmit = 0x487c50 if shc else 0x487d60
    remote = 0x480417 if shc else 0x4805e7
    local = 0x4892be if shc else 0x4893ce
    table = struct.unpack('<I', reader(remote+10, 4))[0]
    handler, stop, stack, source = 0x3df0000, 0x3df1000, 0x4108000, 0x3d00000
    names = ('EAX','EBX','ECX','EDX','ESI','EDI','EBP','ESP','EFLAGS')
    registers = {n: getattr(reg, 'UC_X86_REG_'+n) for n in names}
    cases = 0
    for origin in ('localImmediate', 'remoteImmediate'):
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        machine.mem_map(0x400000, 0x3e00000)
        def read(a,n): return bytes(machine.mem_read(int(a),int(n)))
        def write(a,data): machine.mem_write(int(a),bytes(data))
        def get(a): return struct.unpack('<i',read(a,4))[0]
        def put(a,v): write(a,struct.pack('<I',v & 0xffffffff))
        for address, length in ((schedule,0x22c),(queue,0x1e3),(translate,0x89)):
            write(address,reader(address,length))
        for address, ret in ((fill,12),(copy,12),(clear,4),(transmit,20)):
            write(address,b'\xc2'+struct.pack('<H',ret))
        write(handler,b'\xc3'); put(table+12*4,handler)
        put(base+0x618,1); put(base+actor+4,3); put(base+0x6a4,103)
        for slot in range(1,9): put(base+0x6a8+slot*4,100+slot)
        lua=LuaRuntime(unpack_returned_tuples=True)
        g=lua.globals(); g.source_root=Path(__file__).resolve().parents[1].as_posix()
        g.base=base; g.actor=actor; g.variant=variant
        g.read_integer=get; g.read_byte=lambda a: read(a,1)[0]
        g.read_bytes=lambda a,n: lua.table_from(list(read(a,n)))
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/native']={profile={name=variant}}
package.loaded['code/sessions']={}; package.loaded['code/platform']={}
core={readInteger=read_integer,readByte=read_byte,readBytes=read_bytes}
trace=require('code/multiplayer-trace').new({base=base,sites={actorOffset=actor},tick=function() return 64 end})
trace.file=true; trace.checkNetwork=function() end
trace.gap=function(_,reason,details) captured=details end
''')
        payload=b''; observed=[]; executions=[]; transmitted=[]
        def at_instruction(uc,address,size,data):
            esp=uc.reg_read(reg.UC_X86_REG_ESP)
            if address==fill:
                length,value,destination=(get(esp+i) for i in (4,8,12))
                write(destination,bytes([value & 255])*length)
            elif address==copy:
                length,input_,destination=(get(esp+i) for i in (4,8,12))
                assert destination==base+0x2d834
                write(destination,read(input_,length))
            elif address==handler:
                phase=get(base+0x2d828)
                if phase in (1,2):
                    put(base+0x2d830,len(payload))
                    put(base+0x3c67c+get(base+0x2d824)*1272,0)
                    if phase==1: write(base+0x2d834,payload)
                else:
                    assert phase==0
                    executions.append(read(base+0x2d834,len(payload)))
            elif address==transmit:
                assert get(esp+12)==base+0x2d834 and get(esp+16)==len(payload)
                transmitted.append(read(get(esp+12),len(payload)))
                put(base+0x2d828,0) # stand-in for local delivery by transport
            elif address in (remote,local):
                before={n: uc.reg_read(r) for n,r in registers.items()}
                g.trace.immediateCommand(g.trace,origin)
                assert before=={n: uc.reg_read(r) for n,r in registers.items()}
                observed.append(dict(g.captured.items()))
        machine.hook_add(UC_HOOK_CODE,at_instruction)
        for slot in (0,199):
            for length in (0,10,136,1261,61000):
                payload=bytes((i*29+7)%256 for i in range(length))
                put(base+write_index,slot)
                write(base+0x2d834,b'\xa5'*61000)
                write(base+0x3c67c+slot*1272,b'\x77'*1272)
                write(source,payload)
                args=(12,) if origin=='localImmediate' else (12,103,0,source)
                for n,r in registers.items(): machine.reg_write(r,0x202 if n=='EFLAGS' else 0)
                machine.reg_write(reg.UC_X86_REG_ECX,base)
                machine.reg_write(reg.UC_X86_REG_ESP,stack)
                write(stack,struct.pack('<'+'I'*(len(args)+1),stop,*args))
                machine.emu_start(queue if origin=='localImmediate' else schedule,stop,count=1000)
                assert machine.reg_read(reg.UC_X86_REG_EIP)==stop
                assert machine.reg_read(reg.UC_X86_REG_ESP)==stack+4*(len(args)+1)
                event=observed[-1]
                assert event['data']==payload.hex().upper() and event['size']==length
                assert event['handle']==103 and event['player']==3 and event['category']==12
                assert executions[-1]==payload
                if origin=='localImmediate': assert transmitted[-1]==payload
                cases+=1
        assert len(observed)==10 and len(executions)==10
    print(f'PASS: {variant} {cases} native immediate paths; fixed-buffer payload and Lua evidence agree')
