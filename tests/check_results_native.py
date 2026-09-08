"""Execute the original results-timer branch with and without the replay gate."""
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_ECX


def check_results(reader, lua, root, variant):
    sites = lua.execute((root/'code/engine-sites.lua').read_text())[variant]
    site = sites.resultsTimer
    emitter = lua.execute((root/'code/scoped-code.lua').read_text())
    start, end = site.address, site.address+0x30
    original = reader(start, end-start)
    assert original[5:7] == b'\x76\x29'
    player = struct.unpack_from('<I', original, 8)[0]
    alive = struct.unpack_from('<I', original, 16)[0]
    menu = start+0x2b+5+struct.unpack_from('<i', original, 0x2c)[0]
    gate, scope, mode, stack = 0x4000000, 0x4010000, 0x4010004, 0x4108000
    cases = 0
    for gated in (False, True):
        for enabled in (0, 1):
            for game_mode in (0, 99, 1, 2):
                for elapsed in (0, 7999, 8000, 8001, 60000, 0xffffffff):
                    for survived in (0, 1):
                        machine = Uc(UC_ARCH_X86, UC_MODE_32)
                        machine.mem_map(0x400000, 0x4000000)
                        machine.mem_write(start, original)
                        def put(address, value): machine.mem_write(address, struct.pack('<I', value))
                        put(scope, enabled); put(mode, game_mode); put(player, 1)
                        machine.mem_write(alive+2, struct.pack('<H', survived))
                        machine.mem_write(menu, b'\xc2\x08\x00')
                        machine.reg_write(UC_X86_REG_ESP, stack)
                        machine.reg_write(UC_X86_REG_EAX, elapsed)
                        if gated:
                            machine.mem_write(gate, bytes(emitter.build(site,scope,mode,None,gate).values()))
                            machine.mem_write(start, bytes(emitter.jump(start,gate,5).values()))
                        transitions = []
                        def observe(uc,address,size,data):
                            if address == menu:
                                sp = uc.reg_read(UC_X86_REG_ESP)
                                transitions.append(struct.unpack('<2I',uc.mem_read(sp+4,8)))
                                assert uc.reg_read(UC_X86_REG_ECX) == sites.gameCore
                        machine.hook_add(UC_HOOK_CODE, observe)
                        machine.emu_start(start, end, count=100)
                        held = gated and enabled == 1 and game_mode in (0,99)
                        expected = [(29 if survived else 30, 0)] if elapsed>8000 and not held else []
                        assert transitions == expected, (variant, gated,enabled,game_mode,elapsed,survived)
                        assert machine.reg_read(UC_X86_REG_ESP) == stack
                        cases += 1
    print(f'PASS: {variant} {cases} original/patched victory and defeat timer cases; menu callee is stubbed')
