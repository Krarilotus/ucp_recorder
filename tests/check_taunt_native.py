"""Original AI taunt selection with injected clock/menu/queue boundaries only."""
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg
from native_image import load_image


def check_taunts(path, lua, variant, sites):
    shc = variant == 'SHC'
    start = 0x4d10b0 if shc else 0x4d1300
    base = 0x191d768 if shc else 0x23547d8
    rng = 0x1a279c0 if shc else 0x24baec0
    player = 0x1a275dc if shc else 0x24baadc
    teams = 0x117d548 if shc else 0x1210188
    types = 0x115e0f8 if shc else 0x11f0d38
    weights = 0xb42ac0 if shc else 0xb42c50
    recipients = 0x1a269cc if shc else 0x24b9ecc
    queue = 0x489100 if shc else 0x489210
    site = next(s for s in sites.values() if s['name'] == 'aiTauntReply')
    emitter = lua.execute((Path(__file__).resolve().parents[1]/'code/scoped-code.lua').read_text())
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    load_image(machine, path)
    def get(address): return struct.unpack('<I', machine.mem_read(address, 4))[0]
    def put(address, value): machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
    menu = start+0x14+struct.unpack('<i', machine.mem_read(start+0x10,4))[0]
    clock_import = get(start+0x38)
    clock, stop, owner, scope = 0x3df2000, 0x3df1000, 0x3e00000, 0x3df3000
    machine.mem_write(menu, b'\xb8\x01\0\0\0\xc3')
    machine.mem_write(clock, b'\xb8'+struct.pack('<I',3001)+b'\xc3')
    put(clock_import,clock)
    machine.mem_write(queue,b'\xc2\x04\0')
    original = bytes(site['bytes'].values())
    assert bytes(machine.mem_read(site['address'],5)) == original
    gate = bytes(emitter.build(site,scope,base+0x618,123,0x4000000).values())
    machine.mem_write(0x4000000,gate)
    calls = []
    def observe(uc,address,size,data):
        if address == queue:
            assert uc.reg_read(reg.UC_X86_REG_ECX) == base
            assert get(uc.reg_read(reg.UC_X86_REG_ESP)+4) == 14
            calls.append((get(base+0x7a850),bytes(uc.mem_read(recipients,40))))
        if address == stop: uc.emu_stop()
    machine.hook_add(UC_HOOK_CODE,observe)

    def run(current,elapsed,enabled,mode,gated,pending=1000,eligible=True,in_menu=True):
        calls.clear()
        machine.mem_write(site['address'], bytes(emitter.jump(site['address'],0x4000000,5).values()) if gated else original)
        put(scope,enabled); put(base+0x618,mode); put(player,1)
        put(owner+0x6d84,pending)
        machine.mem_write(menu,b'\xb8'+struct.pack('<I',int(in_menu))+b'\xc3')
        machine.mem_write(clock,b'\xb8'+struct.pack('<I',(pending+elapsed)&0xffffffff)+b'\xc3')
        for slot in range(9):
            put(base+0x714+slot*4,1 if eligible and slot in (2,4,7) else 0)
            put(teams+slot*4,slot)
            put(types+slot*0x39f4,slot)
            put(weights+slot*8,slot)
            put(weights+slot*8+4,slot+20)
        machine.mem_write(recipients,bytes(40)); put(base+0x7a850,0)
        machine.mem_write(rng,bytes(0x9c50))
        machine.mem_write(rng,struct.pack('<h',current))
        machine.mem_write(rng+8+19999*2,struct.pack('<h',17)); put(rng+0x9c4c,19999)
        before = bytes(machine.mem_read(rng,0x9c50))
        initial = {'EBX':0x1111,'ESI':0x2222,'EDI':0x3333,'EBP':0x4444,
                   'ECX':owner,'ESP':0x4108000,'EFLAGS':0x202}
        for name,value in initial.items(): machine.reg_write(getattr(reg,'UC_X86_REG_'+name),value)
        put(0x4108000,stop)
        # Reused emulator scenarios rewrite the gate/clock/menu instructions.
        # Remove translated blocks so each case executes those current bytes.
        for address,length in ((start,0x1ea),(menu,6),(clock,6)):
            machine.ctl_remove_cache(address,address+length)
        machine.emu_start(start,0,count=3000)
        assert machine.reg_read(reg.UC_X86_REG_EIP) == stop
        assert machine.reg_read(reg.UC_X86_REG_ESP) == 0x4108004
        for name in ('EBX','ESI','EDI','EBP'):
            assert machine.reg_read(getattr(reg,'UC_X86_REG_'+name)) == initial[name]
        expected = in_menu and mode == 99 and pending != 0 and elapsed > 2000 and eligible
        assert len(calls) == int(expected), (variant,current,elapsed,enabled,mode,gated,pending,eligible,in_menu,calls)
        after = bytes(machine.mem_read(rng,0x9c50))
        if not expected or (gated and enabled and mode in (0,99)):
            assert after == before
        else:
            assert get(rng+0x9c4c) == 0 and struct.unpack('<h',after[:2])[0] == 17
        return list(calls), get(owner+0x6d84), after

    count = 0
    for current in (0,1,2,5,7,32767,-1,-32768):
        for elapsed in (0,2000,2001,10000):
            baseline = run(current,elapsed,0,99,False)
            assert run(current,elapsed,0,99,True) == baseline
            active = run(current,elapsed,1,99,True)
            assert active[:2] == baseline[:2] # same chosen speaker/message and timer behavior
            count += 3
    for options in (dict(mode=0),dict(mode=1),dict(mode=2),dict(mode=99,pending=0),
                    dict(mode=99,eligible=False),dict(mode=99,in_menu=False),dict(mode=99,pending=0xfffffff0)):
        baseline = run(5,2001,0,gated=False,**options)
        active = run(5,2001,1,gated=True,**options)
        assert active[:2] == baseline[:2]
        count += 2
    print(f'PASS: {variant} {count} original AI taunt clock, selection, message, RNG and ABI cases')
