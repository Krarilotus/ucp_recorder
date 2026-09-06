"""Execute the original wedding selector and RNG; no callee stand-ins.

The chapel/church/cathedral renderer calls this selector while drawing its
monthly announcement. Its unit scan must remain read-only and its result usable.
"""
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as reg
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from native_image import load_image


def check_weddings(path, lua, variant, sites):
    shc = variant == 'SHC'
    start = 0x539df0 if shc else 0x53a210
    caller = 0x43c2e3 if shc else 0x43c523
    rng = 0x1a279c0 if shc else 0x24baec0
    rng_function = 0x46a800 if shc else 0x46aa20
    history = 0xee0fe8 if shc else 0xee1468
    mode_address = (0x191d768 if shc else 0x23547d8)+0x618
    owner, scope, stop, output = 0x3000000, 0x3df3000, 0x3df1000, 0x3df4000
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    load_image(machine, path)
    def get(address): return struct.unpack('<I', machine.mem_read(address, 4))[0]
    def put(address, value): machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
    original_call = bytes(machine.mem_read(caller, 5))
    assert original_call[0] == 0xe8
    assert caller+5+struct.unpack('<i', original_call[1:])[0] == start
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(bytes(machine.mem_read(start, 0x1e0)), start))
    calls = {i.address for i in instructions if i.mnemonic == 'call'}
    guards = [s for s in sites.values() if s['name'] in ('weddingHusband', 'weddingWife')]
    assert len(guards) == 2 and calls == {s['address'] for s in guards}
    assert all(s['target'] == rng_function for s in guards)
    emitter = lua.execute((Path(__file__).resolve().parents[1]/'code/scoped-code.lua').read_text())
    for index, site in enumerate(guards):
        assert bytes(machine.mem_read(site['address'],5)) == bytes(site['bytes'].values())
        origin = 0x4000000+index*0x1000
        machine.mem_write(origin,bytes(emitter.build(site,scope,mode_address,123,origin).values()))
    writes = set()
    def observe(uc,address,size,data):
        if address == stop: uc.emu_stop()
    def written(uc,access,address,size,value,data):
        if not 0x4100000 <= address < 0x4110000:
            writes.update(range(address,address+size))
    machine.hook_add(UC_HOOK_CODE,observe)
    machine.hook_add(UC_HOOK_MEM_WRITE,written)

    def run(current,index,enabled,mode,gated,eligible=True,repeat=False,crowded=False):
        for i, site in enumerate(guards):
            code = emitter.jump(site['address'],0x4000000+i*0x1000,5) if gated else site['bytes']
            machine.mem_write(site['address'],bytes(code.values()))
        machine.ctl_remove_cache(start,start+0x1e0)
        put(scope,enabled); put(mode_address,mode)
        count = 242 if crowded else 6
        unit_data = bytearray(0x614+count*0x490)
        struct.pack_into('<I',unit_data,0,count)
        # Alternating eligible woodcutters and brewers, plus the no-wife path.
        for slot in range(1,count):
            offset = 0x614+slot*0x490+0x8e
            struct.pack_into('<hh',unit_data,offset-2,1,3 if slot%2 else (17 if eligible else 0))
            unit_data[offset+0x35e] = 20 if slot%2 else 60
        machine.mem_write(owner,bytes(unit_data))
        machine.mem_write(history,bytes(72)); machine.mem_write(output,bytes(8))
        rng_data = bytearray(0x9c50)
        struct.pack_into('<h',rng_data,0,current)
        # Native RNG1 reads at the current index and wraps at 20,000.
        for slot in range(20000): struct.pack_into('<h',rng_data,8+slot*2,(current+slot+3)%32768)
        struct.pack_into('<I',rng_data,0x9c4c,index)
        machine.mem_write(rng,bytes(rng_data))
        before = bytes(machine.mem_read(rng,0x9c50))
        writes.clear()
        results = []
        for _ in range(2 if repeat else 1):
            initial = {'EBX':0x1111,'ESI':0x2222,'EDI':0x3333,'EBP':0x4444,
                       'ECX':owner,'ESP':0x4108000,'EFLAGS':0x202}
            for name,value in initial.items(): machine.reg_write(getattr(reg,'UC_X86_REG_'+name),value)
            put(0x4108000,stop); put(0x4108004,output); put(0x4108008,output+4)
            machine.emu_start(start,0,count=50000)
            assert machine.reg_read(reg.UC_X86_REG_EIP) == stop
            assert machine.reg_read(reg.UC_X86_REG_ESP) == 0x410800c
            for name in ('EBX','ESI','EDI','EBP'):
                assert machine.reg_read(getattr(reg,'UC_X86_REG_'+name)) == initial[name]
            success = machine.reg_read(reg.UC_X86_REG_EAX)
            if not eligible: assert success == 0
            elif not results: assert success == 1, (variant,current,index,enabled,mode,gated)
            if success:
                husband,wife=get(output),get(output+4)
                assert 1 <= husband < count and husband%2 == 1
                assert 1 <= wife < count and wife%2 == 0
                assert get(history) == husband and get(history+4) == wife
            results.append((success,bytes(machine.mem_read(output,8))))
        after=bytes(machine.mem_read(rng,0x9c50))
        assert bytes(machine.mem_read(owner,len(unit_data))) == bytes(unit_data)
        allowed=set(range(history,history+72)) | set(range(output,output+8)) | set(range(rng,rng+0x9c50))
        assert writes <= allowed, (variant,sorted(writes-allowed))
        if not eligible or (gated and enabled == 1 and mode in (0,99)):
            assert after == before
        elif not repeat:
            assert get(rng+0x9c4c) == (index+2)%20000
        return results,bytes(machine.mem_read(history,72)),after

    count=0
    for current in (0,1,7,32767):
        for index in (0,19998,19999):
            for options in ({},{'eligible':False},{'repeat':True},{'crowded':True}):
                baseline=run(current,index,0,99,False,**options)
                assert run(current,index,0,99,True,**options) == baseline
                for mode in (0,99): run(current,index,1,mode,True,**options)
                for mode in (1,2):
                    assert run(current,index,1,mode,True,**options) == baseline
                count+=6
    print(f'PASS: {variant} {count} original wedding selector/RNG, population, history, wrap, SP/MP and ABI cases')
