"""Optional original-binary validation. Requires lupa, uses no native writes."""
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
        for profile_file in ('engine-sites.lua','ui-sites.lua','scoped-sites.lua'):
            sites=lua.execute((root/'code'/profile_file).read_text())[name]
            for site_name,site in sites.items():
                if hasattr(site, 'items'):
                    expected=bytes(site['bytes'].values())
                    assert reader(site['address'],len(expected))==expected, f'{name}: {site_name}'
        print(f'PASS: {name} native patch sites, RNG fields, player layout and menu reference')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('game_directory', type=Path)
    check(parser.parse_args().game_directory)
