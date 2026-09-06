"""Check declared timed payload sizes by executing the original receive phase."""
import struct
from pathlib import Path
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg
from native_image import load_image


def check_layouts(path, lua, variant):
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    load_image(machine, path)
    shc = variant == 'SHC'
    base = 0x191d768 if shc else 0x23547d8
    dispatch = 0x48937f if shc else 0x48948f
    def get(address): return struct.unpack('<I', machine.mem_read(address, 4))[0]
    def put(address, value): machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
    table = get(dispatch+11)
    schema = lua.execute((Path(__file__).resolve().parents[1]/'code/command-layouts.lua').read_text())
    stop = 0x3df1000
    def observe(uc, address, size, data):
        if address == stop: uc.emu_stop()
    machine.hook_add(UC_HOOK_CODE, observe)
    # Audit the full original table, not just the recorder's allowlist. Every
    # omitted timed handler must have a deliberate non-gameplay explanation.
    timed_exclusions = {
        8:'removed',30:'removed',32:'removed',39:'native save/load',
        54:'resynchronization start',77:'player disconnection',83:'multiplayer alliances',
    }
    if shc: timed_exclusions[119]='Extreme-only tactical powers'
    for category in range(120):
        put(base+0x2d824,0); put(base+0x2d828,2); put(base+0x2d830,0xffffffff)
        put(base+0x3c67c,777); put(0x4108000,stop)
        machine.reg_write(reg.UC_X86_REG_ESP,0x4108000)
        machine.emu_start(get(table+4*category),0,count=10000)
        assert machine.reg_read(reg.UC_X86_REG_EIP)==stop,(variant,category)
        size,time=get(base+0x2d830),get(base+0x3c67c)
        expected=schema(category,variant)
        if expected is not None:
            assert (size,time)==(expected,777),(variant,category,size,time)
        elif size != 0xffffffff and time != 0:
            assert category in timed_exclusions, f'{variant}: unaudited timed command {category}, size {size}'
    count = 0
    for category in range(123):
        expected = schema(category, variant)
        if expected is None and category != 14:
            continue
        for slot in (0, 199):
            for timestamp in (1, 777, 2147483647):
                put(base+0x2d824, slot); put(base+0x2d828, 2)
                put(base+0x2d830, 0xffffffff)
                put(base+0x3c67c+1272*slot, timestamp)
                put(0x4108000, stop)
                initial = {'EBX':0x1111, 'ESI':0x2222, 'EDI':0x3333, 'EBP':0x4444,
                           'ESP':0x4108000, 'EFLAGS':0x202}
                for name, value in initial.items(): machine.reg_write(getattr(reg, 'UC_X86_REG_'+name), value)
                machine.emu_start(get(table+4*category), 0, count=3000)
                assert machine.reg_read(reg.UC_X86_REG_EIP) == stop, (variant, category)
                assert machine.reg_read(reg.UC_X86_REG_ESP) == 0x4108004
                for name in ('EBX', 'ESI', 'EDI', 'EBP'):
                    assert machine.reg_read(getattr(reg, 'UC_X86_REG_'+name)) == initial[name]
                assert get(base+0x2d830) == (544 if category == 14 else expected), (variant, category)
                assert get(base+0x3c67c+1272*slot) == (0 if category == 14 else timestamp), (variant, category)
                count += 1
    print(f'PASS: {variant} all 120 command entries audited; {count} original supported layout/ring/timestamp cases, no handler stand-ins')
