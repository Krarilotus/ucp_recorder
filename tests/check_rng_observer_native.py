"""Original RNG execution with/without the Lua observer callback; UCP bridge is a stand-in."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP,
    UC_X86_REG_ESP, UC_X86_REG_EFLAGS)


def check_rng_observer(reader, lua, native, root, variant):
    lua.globals().nativeObserverProfile = native
    lua.execute('''
package.loaded['code/native']=nativeObserverProfile
rngCallbacks={}; rngObserved={}
core.detourCode=function(callback,address,size) assert(size==6); rngCallbacks[address]=callback end
observerTrace={engine={rng=0x3000000},observe=function(_,event,stream,stack)
 assert(event=='rngCall'); rngObserved[#rngObserved+1]={stream,stack,core.readInteger(stack)}
end}
''')
    observer = lua.execute((root/'code/rng-observer.lua').read_text())
    observer.install(lua.globals().observerTrace)
    registers = dict(EAX=UC_X86_REG_EAX, EBX=UC_X86_REG_EBX, ECX=UC_X86_REG_ECX,
        EDX=UC_X86_REG_EDX, ESI=UC_X86_REG_ESI, EDI=UC_X86_REG_EDI,
        EBP=UC_X86_REG_EBP, ESP=UC_X86_REG_ESP, EFLAGS=UC_X86_REG_EFLAGS)
    cases = 0
    for stream, entry, offset in ((1, 0x46a800, 0x9c4c), (2, 0x46a7d0, 0x9c48)):
        address = native.addr(entry)
        for index in (0, 1, 19998, 19999):
            outcomes = []
            for observed in (False, True):
                machine = Uc(UC_ARCH_X86, UC_MODE_32)
                machine.mem_map(0x400000, 0x200000)
                machine.mem_map(0x3000000, 0x20000)
                machine.mem_write(address, reader(address, 48))
                machine.mem_write(0x3000000+offset, struct.pack('<i', index))
                machine.mem_write(0x3000008+index*2, struct.pack('<h', 12345))
                stack, stop = 0x3018000, 0x500000
                machine.mem_write(stack, struct.pack('<I', stop))
                for i, reg in enumerate(registers.values()):
                    machine.reg_write(reg, i+10)
                machine.reg_write(UC_X86_REG_EFLAGS, 0x202)
                machine.reg_write(UC_X86_REG_ECX, 0x3000000)
                machine.reg_write(UC_X86_REG_ESP, stack)
                lua.globals().core.readInteger = lambda a: struct.unpack('<i', machine.mem_read(a, 4))[0]
                if observed:
                    def at_entry(uc, ip, size, data):
                        if ip != address:
                            return
                        before = {name: uc.reg_read(reg) for name, reg in registers.items()}
                        values = lua.table_from(before)
                        result = lua.globals().rngCallbacks[address](values)
                        assert dict(result.items()) == before
                    machine.hook_add(UC_HOOK_CODE, at_entry)
                machine.emu_start(address, stop, count=30)
                outcomes.append((bytes(machine.mem_read(0x3000000, 0x9c50)),
                                 [machine.reg_read(reg) for reg in registers.values()]))
            assert outcomes[0] == outcomes[1]
            event = lua.globals().rngObserved[len(lua.globals().rngObserved)]
            assert list(event.values()) == [stream, stack, stop]
            cases += 1
    print(f'PASS: {variant} {cases} original RNG/observer pairs including both index wraps; state/registers identical')
