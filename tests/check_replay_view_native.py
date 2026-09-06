"""Execute the original player summary; only pixel/number drawing callees are stand-ins."""
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP)


def check_replay_view(reader, lua, native, root, variant):
    sites = lua.execute((root/'code/ui-sites.lua').read_text())[variant]
    engine = lua.execute((root/'code/engine-sites.lua').read_text())[variant]
    start = sites.playerSummary.address
    instructions = []
    for instruction in Cs(CS_ARCH_X86, CS_MODE_32).disasm(reader(start, 0x500), start):
        instructions.append(instruction)
        if instruction.mnemonic == 'ret': break
    assert instructions[-1].mnemonic == 'ret'
    code = reader(start, instructions[-1].address+1-start)
    targets = {int(i.op_str, 16) for i in instructions if i.mnemonic == 'call'}
    width = 0x46a4d0 if variant == 'SHC' else 0x46a6f0
    draw = 0x46a2c0 if variant == 'SHC' else 0x46a4e0
    assert targets == {width, draw}, 'Unexpected gameplay dependency in summary renderer'
    machine = Uc(UC_ARCH_X86, UC_MODE_32)
    machine.mem_map(0x400000, 0x4000000)
    machine.mem_write(start, code)
    machine.mem_write(width, b'\xb8\x08\x00\x00\x00\xc2\x08\x00')
    machine.mem_write(draw, b'\xc2\x1c\x00')
    slot = native.addr(0x1a275dc)
    actor = native.addr(0x191d768)+engine.actorOffset
    data = engine.playerResources-0x4d0
    stack, stop = 0x4000000, 0x4100000
    def read32(address): return struct.unpack('<i', machine.mem_read(address, 4))[0]
    def write32(address, value): machine.mem_write(address, struct.pack('<i', value))
    lua.globals().core.readInteger = read32
    lua.globals().core.writeInteger = write32
    lua.globals().replayViewNative = native
    lua.execute("package.loaded['code/native']=replayViewNative")
    view_module = lua.execute((root/'code/replay-view.lua').read_text())
    lua.globals().viewModule = view_module
    lua.execute('''
viewRecorder={mode='play',active=true,status='playing',manifest={player=1},engine={
 singlePlayer=function() return true end,networkState=function()
  local slots={}; for i=1,8 do slots[i]={kind='ai'} end; return {roster=slots}
 end}}
nativeView=viewModule.new(viewRecorder)
''')
    view = lua.globals().nativeView
    drawn, writes = [], []
    def at_call(uc, ip, size, user):
        if ip == draw: drawn.append(read32(uc.reg_read(UC_X86_REG_ESP)+4))
    machine.hook_add(UC_HOOK_CODE, at_call)
    machine.hook_add(UC_HOOK_MEM_WRITE, lambda uc, access, address, size, value, user: writes.append((address, size)))
    saved = {UC_X86_REG_EBX: 31, UC_X86_REG_ESI: 32, UC_X86_REG_EDI: 33, UC_X86_REG_EBP: 34}
    cases = 0
    for selected in range(1, 9):
        for gold, population, capacity, popularity in ((-5,-3,0,1200),(100,22,50,4500),(123456,205,350,9800)):
            for player in range(1,9):
                base = data+player*0x39f4
                write32(base+0x60, popularity if player==selected else 100)
                write32(base+0x74, capacity if player==selected else 1)
                write32(base+0x2180, population if player==selected else 1)
                write32(base+0x4d0+60, gold if player==selected else 1)
            write32(slot, 1); write32(actor, 7)
            before = bytes(machine.mem_read(data, 9*0x39f4))
            rng = native.addr(0x1a279c0)
            before_rng = bytes(machine.mem_read(rng, 0x9c50))
            view.select(view, selected)
            drawn.clear(); writes.clear()
            def render():
                assert read32(slot) == selected
                for reg, value in saved.items(): machine.reg_write(reg, value)
                machine.reg_write(UC_X86_REG_ESP, stack)
                write32(stack, stop)
                machine.emu_start(start, stop, count=1000)
                assert machine.reg_read(UC_X86_REG_ESP) == stack+4
                assert all(machine.reg_read(reg)==value for reg,value in saved.items())
                return 42
            assert view.render(view, render) == 42
            assert drawn == [max(0,gold)]*6+[max(0,population) if capacity else 0]*4+[capacity]*3+[popularity//100]*3
            assert read32(slot)==1 and read32(actor)==7 and lua.globals().viewRecorder.manifest.player==1
            assert bytes(machine.mem_read(data,9*0x39f4)) == before
            assert bytes(machine.mem_read(rng,0x9c50)) == before_rng
            assert all(stack-256<=address<stack or address==sites.textManager.value for address,size in writes)
            cases += 1
    print(f'PASS: {variant} {cases} original player-summary cases; selected stats, restored identity, unchanged player/RNG state; pixel drawing is stubbed')
