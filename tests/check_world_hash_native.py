"""Original native subtotal routine with the actual Lua reader on SHC/Extreme.

Hash callee is deterministic test data, not validation of the hash algorithm.
The UCP bridge is a stand-in: invoke its Lua callback then execute the relocated
11-byte instruction span. Compare native writes and registers with no observer.
"""
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from lupa.luajit21 import LuaRuntime
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as reg

from native_image import load_image


def check_world_hash(path, variant):
    root = Path(__file__).resolve().parents[1]
    base, entry, hasher, delta = (
        (0x191d768, 0x48cc90, 0x46cd30, 0) if variant == 'SHC' else
        (0x23547d8, 0x48cda0, 0x46cf50, 0x5c490))
    # The live engine supplies the match tick. Set the native source after
    # decoding the original MOV rather than trusting an independent address.
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    load_image(machine, path)
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().rootPath = root.as_posix()
    lua.globals().variant = variant
    lua.globals().base = base
    lua.execute("package.path=rootPath..'/?.lua;'..package.path")
    site = lua.eval("require('code/world-hash-sites')[variant]")
    address = site['address']
    original = bytes(site['bytes'].values())
    assert bytes(machine.mem_read(address, len(original))) == original
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(original, address))
    assert [(i.mnemonic, i.size) for i in instructions] == [('cmp', 4), ('lea', 7)]
    # Native beginning loads the global match tick before storing its local
    # advertised tick. Derive that exact absolute operand from the instruction.
    tick_load = bytes(machine.mem_read(entry+0x3e,6))
    assert tick_load[:2] == b'\x8b\x0d' # MOV ECX,[absolute match tick]
    clock = struct.unpack('<I', tick_load[2:])[0]
    stop, stack, trampoline = 0x3df1000, 0x4108000, 0x3df2000
    machine.mem_write(hasher, b'\xc2\x08\x00')
    queue = 0x489100 if variant == 'SHC' else 0x489210
    machine.mem_write(queue, b'\xc2\x04\x00')
    def get(a): return struct.unpack('<I', machine.mem_read(a, 4))[0]
    def put(a, value): machine.mem_write(a, struct.pack('<I', value & 0xffffffff))
    lua.globals().readInteger = lambda a: struct.unpack('<i', machine.mem_read(a, 4))[0]
    lua.globals().readBytes = lambda a,n: lua.table_from(list(machine.mem_read(a,n)))
    lua.globals().playerAddress = base+0x109e74+delta
    lua.execute('''
package.loaded['code/native']={profile={name=variant}}
package.loaded['code/sessions']={}
package.loaded['code/platform']={}
core={readInteger=readInteger,readBytes=readBytes,
 detourCode=function(callback,address,size) assert(size==11); observerCallback=callback end}
engine={base=base,player=function() return core.readInteger(playerAddress) end,
 tick=function() return 128 end,singlePlayer=function() return false end}
trace=require('code/multiplayer-trace').new(engine)
trace.file=true; trace.pendingNativeHashes={}
trace.checkNetwork=function() end -- no transport is emulated by this fixture
require('code/world-hash-observer').install(trace)
''')
    registers = {name:getattr(reg,'UC_X86_REG_'+name) for name in
                 ('EAX','EBX','ECX','EDX','ESI','EDI','EBP','ESP','EFLAGS')}
    writes, subtotal_writes, callbacks, queued = [], [], [], []
    def code(uc, ip, size, data):
        if ip == stop:
            uc.emu_stop()
        elif ip == hasher:
            sp = uc.reg_read(reg.UC_X86_REG_ESP)
            uc.reg_write(reg.UC_X86_REG_EAX, (get(sp+4)^get(sp+8)^0x9e3779b9)&0xffffffff)
        elif ip == queue:
            assert uc.reg_read(reg.UC_X86_REG_ECX)==base
            command=get(uc.reg_read(reg.UC_X86_REG_ESP)+4)
            assert command==12
            queued.append(command)
        elif ip == trampoline:
            before = {name:uc.reg_read(r) for name,r in registers.items()}
            result = lua.globals().observerCallback(lua.table_from(before))
            assert dict(result.items()) == before
            assert not lua.globals().trace.failed, lua.globals().trace.failureReason
            callbacks.append(ip)
    def write(uc, access, a, size, value, data):
        if not stack-0x100 <= a <= stack+8:
            writes.append((a,size,value & ((1<<(size*8))-1)))
        if base+0x7a8e0 <= a < base+0x7aab4:
            subtotal_writes.append(a-base)
    for target in (stop, hasher, trampoline, queue):
        machine.hook_add(UC_HOOK_CODE, code, begin=target, end=target)
    machine.hook_add(UC_HOOK_MEM_WRITE, write)
    pairs = 0
    for player in range(1,9):
        for halted, countdown, dont_send in ((h,c,s) for h,c in ((0,0),(1,0),(0,1)) for s in (0,1)):
            outcomes=[]
            for observed in (False,True):
                machine.mem_write(address, original if not observed else
                                  b'\xe9'+struct.pack('<i',trampoline-address-5)+b'\x90'*6)
                machine.mem_write(trampoline, original+b'\xe9'+struct.pack('<i',address-trampoline-5))
                machine.ctl_remove_cache(address,address+len(original))
                put(base+0xb94,halted); put(base+0x1092ac+delta,countdown)
                put(base+0x109e74+delta,player); put(clock,128)
                lua.execute('trace.pendingNativeHashes={}; trace.failed=false')
                writes.clear(); subtotal_writes.clear(); callbacks.clear(); queued.clear()
                for name,value in {'ESP':stack,'ECX':base,'EBX':0x1111,'ESI':0x2222,'EDI':0x3333,
                                   'EBP':0x4444,'EAX':0,'EDX':0,'EFLAGS':0x202}.items():
                    machine.reg_write(registers[name],value)
                put(stack,stop); put(stack+4,dont_send)
                machine.emu_start(entry,0,count=2000000)
                assert machine.reg_read(reg.UC_X86_REG_EIP)==stop
                assert machine.reg_read(reg.UC_X86_REG_ESP)==stack+8
                assert all(machine.reg_read(registers[n])==v for n,v in
                           {'EBX':0x1111,'ESI':0x2222,'EDI':0x3333,'EBP':0x4444}.items())
                expected=[0x7a8e0+player*48+i*4 for i in range(14)]
                assert subtotal_writes == ([] if halted or countdown else expected)
                samples=lua.globals().trace.pendingNativeHashes
                captured = observed and not halted and not countdown
                assert len(samples)==len(callbacks)==int(captured)
                assert queued==([12] if not halted and not countdown and not dont_send else [])
                if captured:
                    sample=samples[1]
                    assert sample['player']==player and sample['time']==128
                    assert list(sample['domains'].values())==[get(base+a) for a in expected]
                    assert sample['total']==sum(sample['domains'].values())&0xffffffff
                outcomes.append(([machine.reg_read(r) for r in registers.values()],list(writes),list(queued)))
            assert outcomes[0]==outcomes[1], (variant,player,halted,countdown)
            if captured:
                old=samples[1]['domains'][13]
                put(base+0x7a8e0+(player+1)*48,old^0xffffffff)
                assert samples[1]['domains'][13]==old # Lua owns an immediate copy
            pairs+=1
    print(f'PASS: {variant} {pairs} native world-hash observer pairs; 14 stores, all slots, skip paths, ABI and writes')
