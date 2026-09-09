"""Run original spawn prologues and menu-pause queries, without the game process."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_ECX, UC_X86_REG_EAX


def check_spawn_context(reader, lua, root, variant):
    context = lua.execute((root/'code/rng-spawn-context.lua').read_text())
    profile = context.verify(variant)
    start, end = profile.entry, profile.call
    instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(reader(start, end-start), start))
    callees = [int(i.op_str, 16) for i in instructions if i.mnemonic == 'call']
    assert len(callees) == 1  # setUnitValues; two stack arguments
    rng = end+5+struct.unpack('<i', reader(end+1, 4))[0]
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    machine.mem_write(start, reader(start, end-start+5))
    machine.mem_write(callees[0], b'\xc2\x08\x00')
    stack, stop = 0x4000000, 0x4100000
    values = (stop, 2, 4, 120, 160, 8, 1)
    machine.mem_write(stack, struct.pack('<7I', *values))
    machine.reg_write(UC_X86_REG_ESP, stack)
    machine.reg_write(UC_X86_REG_ECX, 0x3000000)
    machine.emu_start(start, rng, count=1000)
    read32 = lambda address: struct.unpack('<i', machine.mem_read(address, 4))[0]
    previous = lua.globals().core.readInteger
    lua.globals().core.readInteger = read32
    sp = machine.reg_read(UC_X86_REG_ESP)
    before = bytes(machine.mem_read(stack-32, 64))
    observed = context.read(profile, end+5, sp, 18106)
    assert dict(observed.items()) == dict(time=18106, caller=stop, player=2, color=4,
        microX=120, microY=160, height=8, unitType=1)
    assert bytes(machine.mem_read(stack-32, 64)) == before
    lua.globals().core.readInteger = previous
    print(f'PASS: {variant} spawn context from original native stack; setUnitValues is stubbed')


def check_menu_pause(reader, lua, root, variant):
    site = lua.execute((root/'code/engine-sites.lua').read_text())[variant].haltingMenu
    code = reader(site.address, len(site.bytes))
    mode = struct.unpack('<I', code[1:5])[0]
    modal = struct.unpack('<I', code[19:23])[0]
    help_modal = struct.unpack('<I', code[36:40])[0]
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    machine.mem_write(site.address, code)
    stack, stop = 0x4000000, 0x4100000
    cases = 0
    for game_mode in (0, 99, 1):
        for dialog in (0, 5, 300):
            for help_id in (0, 28):
                for address, value in ((mode,game_mode),(modal,dialog),(help_modal,help_id),(stack,stop)):
                    machine.mem_write(address, struct.pack('<I', value))
                machine.reg_write(UC_X86_REG_ESP, stack)
                machine.reg_write(UC_X86_REG_ECX, 0x3000000)
                machine.emu_start(site.address, stop, count=40)
                assert machine.reg_read(UC_X86_REG_EAX) == int(game_mode in (0,99) and (dialog!=0 or help_id==28))
                assert machine.reg_read(UC_X86_REG_ESP) == stack+4
                assert machine.reg_read(UC_X86_REG_ECX) == 0x3000000
                cases += 1
    print(f'PASS: {variant} {cases} original native menu-pause queries, including multiplayer exclusion')


def check_fire_context(reader, lua, root, variant):
    context = lua.execute((root/'code/rng-fire-context.lua').read_text())
    profile = context.verify(variant)
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    stack, stop = 0x4000000, 0x4100000
    previous = lua.globals().core.readInteger
    lua.globals().core.readInteger = lambda a: struct.unpack('<i', machine.mem_read(a, 4))[0]
    try:
        for site in context[variant].values():
            start=site.address; code=reader(start,20)
            rng=start+20+struct.unpack('<i',code[-4:])[0]
            machine.mem_write(start,code)
            for values in ((4,120,160,8,3,100),(1,-8,0,256,-1,0)):
                machine.mem_write(stack,struct.pack('<I6i',stop,*values))
                machine.reg_write(UC_X86_REG_ESP,stack)
                machine.emu_start(start,rng,count=20)
                sp=machine.reg_read(UC_X86_REG_ESP)
                before=bytes(machine.mem_read(stack-32,64))
                event=context.read(profile,start+20,sp,76394)
                assert dict(event.items())==dict(zip(
                    ('player','microX','microY','height','spreadParameter','intensity'),values),
                    kind=site.kind,time=76394,caller=stop)
                assert bytes(machine.mem_read(stack-32,64))==before
    finally:
        lua.globals().core.readInteger=previous
    print(f'PASS: {variant} fire caller/argument context from both original prologues; no callee stubs or game writes')
