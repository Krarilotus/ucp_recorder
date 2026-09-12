"""Original tick control flow, including paths bypassing the clock observer.

Subsystem callees are observable stand-ins except the selected height refresh
and navigation countdown paths. This checks phase admission, their native writes
and the stack contract, not a complete world update or the outer loop.
"""
import struct
import re
import pefile
from native_command_fixture import native_command_fixture

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn import x86_const as reg

from native_image import load_image


def check_tick_boundary(path, lua, root, variant):
    sites = lua.execute((root / 'code/engine-sites.lua').read_text())[variant]
    emitter = lua.execute((root / 'code/scoped-code.lua').read_text())
    lua.globals().source_root = root.as_posix()
    lua.execute("package.path=source_root..'/?.lua;'..package.path")
    fixes = lua.eval("require('code/fixes')")
    maintenance = lua.eval("require('code/maintenance-native')")
    image=pefile.PE(data=path.read_bytes()).get_memory_mapped_image()
    scans=[]
    def scan(pattern,start=None):
        scans.append((pattern,start))
        expression=b''.join(b'.' if t=='?' else re.escape(bytes([int(t,16)])) for t in pattern.split())
        offset=(start or 0x400000)-0x400000
        found=re.search(expression,image[offset:],re.DOTALL)
        return 0x400000+offset+found.start() if found else 0
    lua.globals().scan=scan
    lua.globals().read_bytes=lambda a,n:lua.table_from(image[a-0x400000:a-0x400000+n])
    lua.globals().read_int=lambda a:struct.unpack_from('<i',image,a-0x400000)[0]
    lua.globals().commandFixture=lua.table_from(native_command_fixture(variant))
    lua.execute('''
core={AOBScan=scan,scanForAOB=scan,readBytes=read_bytes,readInteger=read_int}
modules={protocol={getNativeCommandInterface=function() return commandFixture end}}
''')
    phase_profile=maintenance.verify()
    entry, clock, ending = (sites[key] for key in ('tickEntry', 'tick', 'tickExit'))
    extreme = variant == 'Extreme'
    sync = 0x23547d8 if extreme else 0x191d768
    in_game = 0x46bd80 if extreme else 0x46bb60
    menu = sites['haltingMenu']['address']
    scope, halt, offline = 0x3e00100, 0x3e00104, 0x3e00108
    playback = 0x3e0010c
    callback, entry_gate, clock_gate, done = 0x3e01000, 0x3e02000, 0x3e03000, 0x3e04000
    stack = 0x3f08000

    def run(patched, stopped, mode, local, paused, save=0, sync_status=0, stop_now=False,
            refresh=False, viewing=False, modal=False, navigation=None, enabled=True, legacy=False,
            reset_period=200, extra_work=None):
        machine = Uc(UC_ARCH_X86, UC_MODE_32)
        load_image(machine, path)
        put = lambda address, value: machine.mem_write(address, struct.pack('<I', value & 0xffffffff))
        get = lambda address: struct.unpack('<I', machine.mem_read(address, 4))[0]
        put(sync + 0x618, mode); put(sync + 0xcbc, save); put(sync + 0xb98, sync_status)
        put(sync + 0x790, 0); put(sync + 0xc6c, 0)  # client; no quit vote
        put(sites['paused'], paused)
        put(sites['gameCore'] + 0x98, 17)
        put(0x2a7afa8 if extreme else 0x1fe7aa8, 8)  # no rotation requested
        put(scope, int(enabled)); put(halt, stopped); put(offline, local); put(playback, int(viewing))
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
            entry_site = entry if legacy else fixes.tickEntry(sites, halt, playback, 0x3e00134)
            for site, flag, target in ((entry_site, halt if legacy else scope, entry_gate), (tick, scope, clock_gate)):
                code = bytes(emitter.build(site, flag, sync + 0x618, None, target, None, offline).values())
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
        navigation_entry = 0x499750 if extreme else 0x4995e0
        countdown = sites['navigationCountdown']
        if navigation is not None:
            # Execute the original decrement/reset and clean-map early return.
            # The dirty-map flood fill is deliberately outside this check.
            targets.remove(navigation_entry)
            put(countdown, navigation)
            # UCP2 Legacy o_increase_path_update_tick_rate changes this one
            # immediate from 200 to 50. Replay admission must preserve it.
            assert machine.mem_read(navigation_entry + 0x38, 10) == b'\xc7\x05' + struct.pack('<II', countdown, 200)
            put(navigation_entry + 0x3e, reset_period)
        calls = []
        # These two maintenance calls have one stack argument; all other
        # reached world-update callees have thiscall's register receiver only.
        pop4 = {0x499750, 0x49b0c0} if extreme else {0x4995e0, 0x49af50}
        pop4.add(sites['queue']['address'])

        def observe(uc, ip, size, unused):
            if ip == navigation_entry and navigation is not None:
                assert get(uc.reg_read(reg.UC_X86_REG_ECX) + 0x6c) == 0
            if ip == done:
                uc.emu_stop()
            elif ip == callback or ip in targets:
                if ip == callback:
                    if stop_now: put(halt, 1)
                else:
                    calls.append(ip)
                sp = uc.reg_read(reg.UC_X86_REG_ESP)
                uc.reg_write(reg.UC_X86_REG_EAX, int(ip == in_game or (ip == menu and modal)))
                uc.reg_write(reg.UC_X86_REG_ESP, sp + 4 + (4 if ip in pop4 else 0))
                uc.reg_write(reg.UC_X86_REG_EIP, get(sp))

        machine.hook_add(UC_HOOK_CODE, observe)
        put(stack, done)
        machine.reg_write(reg.UC_X86_REG_ESP, stack)
        machine.reg_write(reg.UC_X86_REG_ESI, 0x12345678)
        machine.reg_write(reg.UC_X86_REG_ECX, 0x112b538 if extreme else 0x112b0b8)
        start = entry['address']
        if extra_work:
            passes, logical_pause = extra_work
            start = 0x3e08000
            code = maintenance.runner(sites, phase_profile, 0x3e00120, start)
            machine.mem_write(start, bytes(code.values()))
            put(stack + 4, passes); put(stack + 8, logical_pause)
            machine.reg_write(reg.UC_X86_REG_EBX, 0x11223344)
            machine.reg_write(reg.UC_X86_REG_EDI, 0x55667788)
        machine.emu_start(start, done, count=100000)
        assert machine.reg_read(reg.UC_X86_REG_EIP) == done
        assert machine.reg_read(reg.UC_X86_REG_ESP) == stack + 4, (variant, 'tick stack')
        assert machine.reg_read(reg.UC_X86_REG_ESI) == 0x12345678
        if extra_work:
            assert machine.reg_read(reg.UC_X86_REG_EBX) == 0x11223344
            assert machine.reg_read(reg.UC_X86_REG_EDI) == 0x55667788
            assert get(0x3e00134) == 0, 'Internal admission escaped native replay call'
        result = calls, get(sites['gameCore'] + 0x98), get(sites['paused'])
        return result + (get(countdown),) if navigation is not None else result

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
    for mode, local in ((99, 0), (1, 1), (1, 0)):
        for paused, modal in ((1, False), (-1, False), (0, True), (0, False)):
            for initial, reset_period in ((100, 200), (1, 200), (1, 50)):
                options = dict(modal=modal, navigation=initial, reset_period=reset_period)
                original = run(False, 0, mode, local, paused, **options)
                expected = initial - 1 if initial > 1 else reset_period
                assert original[-1] == expected
                # Reproduce the published guard's missing viewer-pause scope.
                old = run(True, 0, mode, local, paused, viewing=True, legacy=True, **options)
                assert old[-1] == expected
                recording = run(True, 0, mode, local, paused, **options)
                assert recording == original
                viewing = run(True, 0, mode, local, paused, viewing=True, **options)
                should_stop = (local or mode == 99) and (paused != 0 or modal)
                assert viewing[-1] == (initial if should_stop else expected), (variant, viewing)
                if should_stop:
                    assert viewing[1] == 17
                    assert viewing[0] == ([] if paused else [menu])
                elif not local and mode != 99:
                    assert viewing == original  # live MP ignores viewer state
                inactive = run(True, 1, mode, local, paused, viewing=True, enabled=False, **options)
                assert inactive == original
                count += 1
    # Replay enters the original coordinator, including the native countdown.
    # Viewer pause/menu must not suppress recorded work; failure halt still must.
    for logical_pause in (1, -1):
        for viewer_pause in (0, 1, -1):
            for period in (50, 200):
                replayed = run(True, 0, 99, 0, viewer_pause, viewing=True, modal=True,
                    navigation=1, reset_period=period, extra_work=(3, logical_pause))
                assert replayed[1:] == (17, viewer_pause & 0xffffffff, period - 2), replayed
                world = 0x456320 if extreme else 0x4560f0
                assert replayed[0].count(world) == (3 if logical_pause == -1 else 0)
                halted = run(True, 1, 99, 0, viewer_pause, viewing=True, navigation=1,
                    extra_work=(3, logical_pause))
                assert halted == ([], 17, viewer_pause & 0xffffffff, 1), halted
                count += 1
    assert len(scans)==2,'Maintenance replay repeated binding discovery'
    print(f'PASS: {variant} tick entry/endpoint halt and passive control flow ({count} cases)')
