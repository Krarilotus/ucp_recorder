"""Original tick control flow, including paths bypassing the clock observer.

Subsystem callees are observable stand-ins: this checks which native phases
execute and the stack contract, not their world-state effects or the outer loop.
"""
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg

from native_image import load_image


def check_tick_boundary(path, lua, root, variant):
    sites = lua.execute((root / 'code/engine-sites.lua').read_text())[variant]
    emitter = lua.execute((root / 'code/scoped-code.lua').read_text())
    entry, clock, ending = (sites[key] for key in ('tickEntry', 'tick', 'tickExit'))
    extreme = variant == 'Extreme'
    sync = 0x23547d8 if extreme else 0x191d768
    in_game = 0x46bd80 if extreme else 0x46bb60
    menu = sites['haltingMenu']['address']
    scope, halt, offline = 0x3e00100, 0x3e00104, 0x3e00108
    callback, entry_gate, clock_gate, done = 0x3e01000, 0x3e02000, 0x3e03000, 0x3e04000
    stack = 0x3f08000

    def run(patched, stopped, mode, local, paused, save=0, sync_status=0, stop_now=False, refresh=False):
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        load_image(machine, path)
        put = lambda address, value: machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
        get = lambda address: struct.unpack('<I', machine.mem_read(address, 4))[0]
        put(sync + 0x618, mode); put(sync + 0xcbc, save); put(sync + 0xb98, sync_status)
        put(sync + 0x790, 0); put(sync + 0xc6c, 0)  # client; no quit vote
        put(sites['paused'], paused)
        put(sites['gameCore'] + 0x98, 17)
        put(0x2a7afa8 if extreme else 0x1fe7aa8, 8)  # no rotation requested
        put(scope, 1); put(halt, stopped); put(offline, local)
        tile_map = 0x2526708 if extreme else 0x1a93208
        refresh_entry = 0x501da0 if extreme else 0x501a20
        put(tile_map + 0x5548b8, 2 if refresh else 0)
        native = bytes(machine.mem_read(entry['address'], 0x346))
        instructions = list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(native, entry['address']))
        assert instructions[-1].mnemonic == 'jmp'
        assert instructions[-1].address + instructions[-1].size == entry['address'] + len(native)
        targets = set()
        for ins in instructions:
            if ins.bytes[0] in (0xe8, 0xe9) and ins.size == 5:
                target = ins.address + 5 + struct.unpack('<i', ins.bytes[1:])[0]
                if not entry['address'] <= target < entry['address'] + len(native):
                    targets.add(target)
        if patched:
            tick = lua.table_from(dict(address=clock['address'], bytes=clock['bytes'], kind='raw',
                patch='tick', callback=callback, halt=halt, skipTick=ending['address']))
            for site, enabled, target in ((entry, halt, entry_gate), (tick, scope, clock_gate)):
                code = bytes(emitter.build(site, enabled, sync + 0x618, None, target, None, offline).values())
                machine.mem_write(target, code)
                machine.mem_write(site['address'], bytes(emitter.jump(site['address'], target, len(site['bytes'])).values()))
            # Use the production view/pause gates too. The refresh routine
            # below still executes; it must not permit an unclocked world step.
            scoped = lua.execute((root / 'code/scoped-sites.lua').read_text())[variant]
            for index, site in enumerate(s for s in scoped.values() if s['name'] in ('pause', 'pausedCamera')):
                target = 0x3e05000 + index * 0x1000
                machine.mem_write(target, bytes(emitter.build(site, scope, sync + 0x618, None,
                    target, None, offline).values()))
                machine.mem_write(site['address'], bytes(emitter.jump(site['address'], target, len(site['bytes'])).values()))
        if refresh:
            targets.remove(refresh_entry)  # execute its real 256-height update
            targets.add(0x4f6e70 if extreme else 0x4f6ae0)  # changed-layer rebuild stand-in
        calls = []
        # These two maintenance calls have one stack argument; all other
        # reached world-update callees have thiscall's register receiver only.
        pop4 = {0x499750, 0x49b0c0} if extreme else {0x4995e0, 0x49af50}
        pop4.add(sites['queue']['address'])

        def observe(uc, ip, size, unused):
            if ip == done:
                uc.emu_stop()
            elif ip == callback or ip in targets:
                if ip == callback:
                    if stop_now: put(halt, 1)
                else:
                    calls.append(ip)
                sp = uc.reg_read(reg.UC_X86_REG_ESP)
                uc.reg_write(reg.UC_X86_REG_EAX, int(ip == in_game))
                uc.reg_write(reg.UC_X86_REG_ESP, sp + 4 + (4 if ip in pop4 else 0))
                uc.reg_write(reg.UC_X86_REG_EIP, get(sp))

        machine.hook_add(UC_HOOK_CODE, observe)
        put(stack, done)
        machine.reg_write(reg.UC_X86_REG_ESP, stack)
        machine.reg_write(reg.UC_X86_REG_ESI, 0x12345678)
        machine.reg_write(reg.UC_X86_REG_ECX, 0x112b538 if extreme else 0x112b0b8)
        machine.emu_start(entry['address'], done, count=10000)
        assert machine.reg_read(reg.UC_X86_REG_EIP) == done
        assert machine.reg_read(reg.UC_X86_REG_ESP) == stack + 4, (variant, 'tick stack')
        assert machine.reg_read(reg.UC_X86_REG_ESI) == 0x12345678
        return calls, get(sites['gameCore'] + 0x98), get(sites['paused'])

    count = 0
    for paused, save, syncing in ((0, 0, 0), (1, 0, 0), (-1, 0, 0), (0, 1, 0),
                                  (0, 0, 1), (0, 0, 2), (0, 0, 3), (0, 0, 10)):
        for mode, local in ((99, 0), (1, 1), (1, 0)):
            original = run(False, 0, mode, local, paused, save, syncing)
            assert run(True, 0, mode, local, paused, save, syncing) == original
            stopped = run(True, 1, mode, local, paused, save, syncing)
            if local or mode == 99:
                assert stopped == ([], 17, paused & 0xffffffff), (variant, stopped)
            else:
                assert stopped == original, (variant, 'live MP affected by stale halt')
            count += 1
    # A callback detecting the endpoint must return before maintenance in the
    # same invocation, not merely prevent the following invocation.
    for mode, local in ((99, 0), (1, 1)):
        stopped = run(True, 0, mode, local, 0, stop_now=True)
        assert stopped == ([in_game, menu], 17, 0), (variant, stopped)
        count += 1
    paused_calls, tick, _ = run(False, 0, 99, 0, 1)
    assert tick == 17 and len(paused_calls) > 2  # clock omitted, maintenance reached
    for mode, local in ((99, 0), (1, 1), (1, 0)):
        original = run(False, 0, mode, local, 1, refresh=True)
        observed = run(True, 0, mode, local, 1, refresh=True)
        world_update = 0x422e30 if extreme else 0x422e20
        assert world_update in original[0] and original[1] == 17
        if local or mode == 99:
            assert world_update not in observed[0] and observed[1] == 17
            assert run(True, 1, mode, local, 1, refresh=True) == ([], 17, 1)
        else:
            assert observed == original  # never change live multiplayer's rules
        count += 1
    print(f'PASS: {variant} tick entry/endpoint halt and passive control flow ({count} cases)')
