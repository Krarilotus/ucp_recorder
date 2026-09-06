"""Optional original-binary validation. Requires lupa/capstone/unicorn; no native writes."""
from pathlib import Path
import argparse
import struct
from lupa.luajit21 import LuaRuntime


def image_reader(path):
    image = path.read_bytes()
    pe = struct.unpack_from('<I', image, 0x3c)[0]
    assert image[pe:pe+4] == b'PE\0\0'
    sections = struct.unpack_from('<H', image, pe+6)[0]
    optional_size = struct.unpack_from('<H', image, pe+20)[0]
    base = struct.unpack_from('<I', image, pe+24+28)[0]
    headers = pe+24+optional_size

    def read(address, size):
        rva = address-base
        for i in range(sections):
            _, start, raw_size, raw = struct.unpack_from('<IIII', image, headers+i*40+8)
            if start <= rva and rva+size <= start+raw_size:
                return image[raw+rva-start:raw+rva-start+size]
        raise ValueError(f'Address outside original file: {address:x}')
    return read


def check(folder):
    root = Path(__file__).resolve().parents[1]
    for name, file in [('SHC', 'Stronghold Crusader.exe'), ('Extreme', 'Stronghold_Crusader_Extreme.exe')]:
        reader = image_reader(folder/file)
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.globals().read_bytes = lambda address, size: lua.table_from(list(reader(address, size)))
        lua.execute('core={readBytes=read_bytes}')
        native = lua.execute((root/'code/native.lua').read_text())
        profile = native.verify()
        assert profile['name'] == name
        rng = native.addr(0x1a279c0)
        assert native.addr(0x1a3160c) == rng+0x9c4c
        synchrony = native.addr(0x191d768)
        assert native.addr(0x191de0c) == synchrony+0x6a4
        offset = 0x109e74 if name == 'SHC' else 0x166304
        assert native.addr(0x1a275dc) == synchrony+offset
        menu = native.addr(0x59ab30)
        assert reader(menu, 1) == b'\x68'
        assert struct.unpack('<I', reader(menu+1, 4))[0] == native.addr(0x5e9848)
        for profile_file in ('engine-sites.lua','ui-sites.lua','scoped-sites.lua','network-sites.lua'):
            sites=lua.execute((root/'code'/profile_file).read_text())[name]
            for site_name,site in sites.items():
                if hasattr(site, 'items'):
                    expected=bytes(site['bytes'].values())
                    assert reader(site['address'],len(expected))==expected, f'{name}: {site_name}'
        ui=lua.execute((root/'code/ui-sites.lua').read_text())[name]
        pause=ui['pauseArray']['value']
        assert struct.unpack('<I',reader(pause+9*80,4))[0]==0x66
        for index in range(1,9):
            x,y,width,height=struct.unpack('<4i',reader(pause+index*80+4,16))
            assert x==100 and width==300 and height==27 and y+height<342
        # Full-instruction WinProc prologue and the shared stdcall/thiscall
        # stack layout used by installInput's unused-ECX bridge.
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        proc=ui['windowProc']
        ins=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(reader(proc['address'],8),proc['address']))
        assert [i.mnemonic for i in ins]==['sub','mov'] and sum(i.size for i in ins)==8
        # Decode the complete mood-selection function, including conditional
        # branches: checking only known patch sites would miss an extra RNG call.
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        start=0x47a340 if name=='SHC' else 0x47a510
        rng_call=0x46a800 if name=='SHC' else 0x46aa20
        calls=set()
        for instruction in Cs(CS_ARCH_X86,CS_MODE_32).disasm(reader(start,0x212),start):
            if instruction.bytes[0]==0xe8 and len(instruction.bytes)==5:
                target=instruction.address+5+struct.unpack('<i',instruction.bytes[1:])[0]
                if target==rng_call: calls.add(instruction.address)
        scoped=lua.execute((root/'code/scoped-sites.lua').read_text())[name]
        guards={site['address'] for site in scoped.values() if site['name'].startswith('moodMusic')}
        assert len(calls)==7 and calls==guards, f'{name}: incomplete mood-music RNG guards'
        # Entire audited audio functions, ending before their trailing jump tables.
        # Count actual instructions, not byte patterns inside operands/data.
        audio_functions = [
            (0x44bce0,0x44bf10,0x701,{'ambientSound'}),
            (0x471720,0x471940,0xcf,{'resourceSpeech'}),
            (0x47a130,0x47a300,0x80,{'audioLaunch'}),
            (0x47ab10,0x47ace0,0x424,{'battleMusic1','battleMusic2'}),
            (0x47b890,0x47ba60,0x68d,{'ambientMusic'}),
        ]
        for shc,extreme,size,names in audio_functions:
            start=shc if name=='SHC' else extreme
            instructions=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(reader(start,size),start))
            assert instructions[-1].address+instructions[-1].size==start+size
            calls={i.address for i in instructions if i.bytes[0]==0xe8 and len(i.bytes)==5
                and i.address+5+struct.unpack('<i',i.bytes[1:])[0]==rng_call}
            guards={s['address'] for s in scoped.values() if s['name'] in names}
            assert len(calls)==len(names) and calls==guards, f'{name}: incomplete {names} RNG guards'
        from check_presentation_native import check_heads_placement
        check_heads_placement(reader,lua,name,scoped)
        from check_command_layouts_native import check_layouts
        check_layouts(folder/file,lua,name)
        from check_production_native import check_production
        check_production(folder/file,name)
        from check_taunt_native import check_taunts
        check_taunts(folder/file,lua,name,scoped)
        from check_wedding_native import check_weddings
        check_weddings(folder/file,lua,name,scoped)
        from check_network_native import check_system_branch
        network=lua.execute((root/'code/network-sites.lua').read_text())[name]
        check_system_branch(reader,name,network['systemMessage'])
        from check_immediate_native import check_immediate
        check_immediate(reader,name)
        from check_rng_observer_native import check_rng_observer
        check_rng_observer(reader,lua,native,root,name)
        from check_replay_view_native import check_replay_view
        check_replay_view(reader,lua,native,root,name)
        from check_dispatch_native import check_dispatch
        check_dispatch(reader,name)
        from check_world_hash_native import check_world_hash
        check_world_hash(folder/file,name)
        print(f'PASS: {name} native patch sites, RNG fields, player layout and menu reference')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('game_directory', type=Path)
    check(parser.parse_args().game_directory)
