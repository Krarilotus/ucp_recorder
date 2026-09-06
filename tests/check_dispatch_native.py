"""Run the Lua replay engine with original x86 scheduling/selection/dispatch.

Unicorn supplies an isolated address space; no game process is opened. UCP's
bridge is represented by callbacks. Memory helpers and a four-byte test command
handler are stand-ins; scheduler, selector, translator and dispatcher are the
original executable instructions. This is not a live UCP hook/ABI test.
"""
from pathlib import Path
import struct
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg

ROOT=Path(__file__).resolve().parents[1]


def check_dispatch(reader,variant):
    shc=variant=='SHC'
    base=0x191d768 if shc else 0x23547d8
    tick=0x1fe7da8 if shc else 0x2a7b2a8
    actor=0x109e70 if shc else 0x166300
    schedule=0x480210 if shc else 0x4803e0
    selector=0x480440 if shc else 0x480610
    dispatch=0x4892f0 if shc else 0x489400
    translator=0x47eaf0 if shc else 0x47ecc0
    fill=0x4718c0 if shc else 0x471ae0
    copy=0x471830 if shc else 0x471a50
    execute=0x48937f if shc else 0x48948f
    table=struct.unpack('<I',reader(execute+11,4))[0]
    handler,stop_address=0x3df0000,0x3df1000
    names=('EAX','EBX','ECX','EDX','ESI','EDI','EBP','ESP','EFLAGS')
    registers={name:getattr(reg,'UC_X86_REG_'+name) for name in names}

    def scenario(replay,capture=False):
        machine=Uc(UC_ARCH_X86,UC_MODE_32)
        machine.mem_map(0x400000,0x3e00000)
        def read(a,n): return bytes(machine.mem_read(int(a),int(n)))
        def write(a,data): machine.mem_write(int(a),bytes(data))
        def get(a): return struct.unpack('<i',read(a,4))[0]
        def put(a,v): write(a,struct.pack('<I',int(v)&0xffffffff))
        for a,size in ((schedule,0x22c),(selector,0x140),(dispatch,0xcb),(translator,0x89)):
            write(a,reader(a,size))
        local_queue=0x489100 if shc else 0x489210
        transmit=0x487c50 if shc else 0x487d60
        if capture:
            write(local_queue,reader(local_queue,0x1e3))
            write(transmit,b'\xc2\x14\x00') # transport is outside this queue test
        write(fill,b'\xc2\x0c\x00'); write(copy,b'\xc2\x0c\x00'); write(handler,b'\xc3')
        put(table+15*4,handler)
        write(handler+4,b'\xc3'); put(table,handler+4)
        put(base+0x618,99); put(base+actor+4,3)
        hooks,detours={},{}
        observed=[]
        inferred_size=[4]
        allocator=[0x3c00000]
        lua=LuaRuntime(unpack_returned_tuples=True)
        def allocate(size,*unused):
            a=allocator[0]; allocator[0]+=int(size)+16; return a
        def expose(address,count,thiscall):
            return lambda *args: call(address,args,thiscall)
        def hook(callback,address,*unused):
            hooks[int(address)]=callback
            return lambda *args: 0x7f00 # ask the emulator to run the original body
        g=lua.globals()
        g.source_root=ROOT.as_posix(); g.variant=variant
        g.native_address=lambda a: {0x191d768:base,0x1a279c0:0x1a279c0 if shc else 0x24baec0,
            0x480210:schedule,0x1a275dc:base+actor+4,0x1fe7da8:tick}[a]
        g.read_integer=get; g.write_integer=put
        g.read_bytes=lambda a,n: lua.table_from(list(read(a,n)))
        g.write_bytes=lambda a,b: write(a,list(b.values()))
        g.read_byte=lambda a: read(a,1)[0]
        g.write_byte=lambda a,v: write(a,bytes([int(v)]))
        g.allocate=allocate; g.expose=expose; g.hook=hook
        g.detour=lambda callback,address,*args: detours.__setitem__(int(address),callback)
        g.write_string=lambda a,s: write(a,s.encode())
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/native']={profile={name=variant},addr=native_address}
core={allocate=allocate,allocateCode=allocate,exposeCode=expose,hookCode=hook,detourCode=detour,
 readInteger=read_integer,writeInteger=write_integer,readBytes=read_bytes,writeBytes=write_bytes,
 readByte=read_byte,writeByte=write_byte,writeCode=write_bytes,writeString=write_string}
engine=require('code/engine').new(require('code/engine-sites')[variant])
recorder={mode='play',status='playing',active=true,manifest={player=3,variant=variant}}
function recorder:feed() end
function recorder:guard(f)
 local ok,reason=pcall(f)
 if not ok then self.status='error'; self.error=reason; engine:abortPlayback() end
 return ok
end
engine:install(recorder)
''')
        engine=g.engine
        if capture:
            lua.execute('''
recorder.mode='record'; recorder.status='recording'; recorder.commands={}
function recorder:onExecutedCommand(command) self.commands[#self.commands+1]=command end
''')

        def call(address,args=(),thiscall=0):
            # Native exposeCode executes outside an existing emulation call.
            values=(0x1111,0x2222,base if thiscall else 0x3333,0x4444,0x5555,0x6666,0x7777,0x4108000,0x202)
            for r,v in zip(registers.values(),values): machine.reg_write(r,v)
            args=list(args)
            if thiscall: machine.reg_write(reg.UC_X86_REG_ECX,args.pop(0))
            put(0x4108000,stop_address)
            for i,value in enumerate(args): put(0x4108004+i*4,value)
            machine.emu_start(address,0,count=1000000)
            assert machine.reg_read(reg.UC_X86_REG_EIP)==stop_address
            assert machine.reg_read(reg.UC_X86_REG_ESP)==0x4108004+len(args)*4
            for r,v in ((reg.UC_X86_REG_EBX,0x2222),(reg.UC_X86_REG_ESI,0x5555),
                        (reg.UC_X86_REG_EDI,0x6666),(reg.UC_X86_REG_EBP,0x7777)):
                assert machine.reg_read(r)==v
            return machine.reg_read(reg.UC_X86_REG_EAX)

        def observe(uc,address,size,data):
            if address==stop_address: uc.emu_stop(); return
            esp=uc.reg_read(reg.UC_X86_REG_ESP)
            if address==fill:
                count,value,destination=(get(esp+i) for i in (4,8,12))
                write(destination,bytes([value&255])*count)
            elif address==copy:
                count,source,destination=(get(esp+i) for i in (4,8,12))
                write(destination,read(source,count))
            elif address==handler:
                if get(base+0x2d828)==2: put(base+0x2d830,inferred_size[0])
                elif get(base+0x2d828)==1 and capture:
                    slot=get(base+0x2d824)
                    put(base+0x3c67c+slot*1272+10,sequence)
                    put(base+0x2d830,4)
                elif get(base+0x2d828)==0:
                    slot=get(base+0x2d824)
                    observed.append((get(tick),slot,get(base+actor),get(base+0x3c67c+slot*1272+10)))
                else: raise AssertionError('unexpected command phase')
            elif address==selector and replay:
                # Commands were admitted through the original scheduler before
                # this call; avoid nested Unicorn execution inside its hook.
                result=hooks[address](base)
                assert result!=0x7f00
                uc.reg_write(reg.UC_X86_REG_EAX,result)
                uc.reg_write(reg.UC_X86_REG_EIP,get(esp))
                uc.reg_write(reg.UC_X86_REG_ESP,esp+4)
                return
            if address in detours and (replay or capture or address==engine['sites']['copySize']['address']):
                assert not capture or address!=engine['sites']['copySize']['address'], 'local input used receive-copy path'
                values=lua.table_from({name:uc.reg_read(r) for name,r in registers.items()})
                returned=detours[address](values)
                for name,r in registers.items(): uc.reg_write(r,int(returned[name]))
            elif address==engine['sites']['execute']['address'] and not replay:
                # install() replaced this MOVSX with NOPs; reproduce that one
                # original instruction when demonstrating baseline selection.
                category=read(base+uc.reg_read(reg.UC_X86_REG_ECX)+0x3c684,1)[0]
                uc.reg_write(reg.UC_X86_REG_EDX,category)
        machine.hook_add(UC_HOOK_CODE,observe)
        put(base+engine['sites']['writeIndexOffset'],199)
        sequence=0
        for now in range(10,16) if replay or capture else (10,):
            put(tick,now)
            count=100 if replay or capture else 2
            for _ in range(count):
                sequence+=1
                command=lua.table_from(dict(commandCategory=15,player=3,time=now,size=4,
                    data=struct.pack('<I',sequence).hex()))
                if capture:
                    call(local_queue,(base,15),1)
                else:
                    engine.scheduleCommand(engine,command)
            call(dispatch,(base,),1)
            if replay:
                assert g.recorder['status']=='playing',g.recorder['error']
                assert engine['journal']['executed']==sequence
                assert not engine.commandsPending(engine)
        if replay:
            assert [r[3] for r in observed]==list(range(1,601))
            assert all(r[2]==3 for r in observed)
            assert [r[0] for r in observed]==[t for t in range(10,16) for _ in range(100)]
            # Actual native enqueue mutates scratch/index before returning.
            # A rejected inferred length must restore every saved queue byte.
            slot=get(base+engine['sites']['writeIndexOffset'])
            address=base+0x3c67c+slot*1272
            before=read(address,1272)
            offsets=(engine['sites']['writeIndexOffset'],0x2d824,0x2d828,0x2d830,
                engine['sites']['writeIndexOffset']+4)
            scratch={offset:get(base+offset) for offset in offsets}
            inferred_size[0]=8
            ok,reason=lua.eval('function(c) return pcall(engine.scheduleCommand,engine,c) end')(
                lua.table_from(dict(commandCategory=15,player=3,time=16,size=4,data='01000000')))
            assert not ok and 'payload size or source differs' in reason
            assert read(address,1272)==before
            assert all(get(base+offset)==value for offset,value in scratch.items())
            assert not engine.commandsPending(engine) and engine['expectedSize'] is None
        elif capture:
            commands=list(g.recorder['commands'].values())
            assert g.recorder['status']=='recording',g.recorder['error']
            assert len(commands)==600 and len(observed)==600
            assert [int(c['data'],16) for c in commands]==[
                int.from_bytes(struct.pack('<I',row[3]),'big') for row in observed]
            assert sorted(row[3] for row in observed)==list(range(1,601))
            assert all(c['player']==3 and c['time']==row[0] for c,row in zip(commands,observed))
            assert not list(engine['received'].items())
        else:
            assert [r[3] for r in observed]==[2,1],observed
        return observed

    scenario(False)
    scenario(True)
    scenario(False,True)
    print(f'PASS: {variant} native ring-wrap reorder reproduced; 600 replay dispatches and 600 local captures; native size-failure rollback verified')
