"""Resolve production UI bindings against a private PE and the actual UI owner.

No process is launched. The CFFI boundary returns pointer numbers; native calling
conventions are covered by the existing original-instruction presentation checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

import pefile
from lupa.lua54 import LuaRuntime


def check(reference, variant, ui_game, framework_code):
    root = Path(__file__).resolve().parents[1]
    raw = reference.read_bytes()
    pe = pefile.PE(data=raw)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = bytearray(pe.get_memory_mapped_image())
    lua = LuaRuntime(unpack_returned_tuples=True)
    scans, matches, cache = [], {}, {}

    def scan(pattern, start=None, stop=None):
        scans.append((pattern, start, stop))
        expression = b''.join(b'.' if t == '?' else re.escape(bytes([int(t, 16)]))
                              for t in pattern.split())
        found = re.search(expression, image[max(0, (start or base)-base):
                                           (stop-base) if stop else None], re.DOTALL)
        address = (max(base, start or base) + found.start()) if found else 0
        if start is None:
            matches[pattern] = address
        return address

    def aob(pattern, start=None, stop=None):
        if start is not None or stop is not None:
            return scan(pattern, start, stop)
        # The framework cache validates its previously matched bytes. This test
        # deliberately bypasses cache hits during negative cases below.
        result = scan(pattern)
        cache[pattern] = result
        return result

    def read(address, count):
        assert base <= address and address + count <= base + len(image), hex(address)
        return bytes(image[address-base:address-base+count])

    g = lua.globals()
    g.source_root = root.as_posix()
    g.py_scan, g.py_aob = scan, aob
    g.py_bytes = lambda a, n: lua.table_from(read(a, n))
    g.py_int = lambda a: struct.unpack('<i', read(a, 4))[0]
    g.py_byte = lambda a: read(a, 1)[0]
    lua.execute("""
package.path=source_root..'/?.lua;'..package.path
log=function() end
core={AOBScan=py_aob,scanForAOB=py_scan,readBytes=py_bytes,readInteger=py_int,readByte=py_byte}
package.loaded.core=core
ffi={cast=function(_,p) return p end,tonumber=tonumber}
modules={cffi={cffi=function() return ffi end}}
""")
    g.utils = lua.execute((framework_code/'utils.lua').read_text(encoding='utf-8'))
    game = lua.execute(ui_game.read_text(encoding='utf-8'))
    expected = lua.execute((root/'tests/fixtures/ui-sites.lua').read_text())[variant]
    # The manager exposes this pointer in its initialized state. Verify its
    # production extraction against the image before supplying that owner state.
    _, stack = g.utils.AOBExtract('8B ? I(? ? ? ?) 89 50 24')
    assert stack == expected.modalStack.value
    g.game_owner, g.stack_owner = game, stack
    lua.execute("api={game=game_owner,manager={getState=function() return {modalMenuStackTop=stack_owner} end}}")
    resolver = lua.execute((root/'code/ui-sites.lua').read_text())
    owner_scans = len(scans)
    sites = resolver.resolve(g.api, g.ffi)
    resolution_scans = scans[owner_scans:]
    for name, old in expected.items():
        current = sites[name]
        assert current is not None, name
        if old.value is not None:
            assert current.value == old.value, (name, current.value, old.value)
        else:
            assert current.address == old.address, (name, current.address, old.address)
            assert list(current.bytes.values()) == list(old.bytes.values()), name
    b = bytes(expected.buildingAndStatus.bytes.values())
    assert sites.window.value == struct.unpack('<I', b[2:6])[0]-0x5c
    assert len(resolution_scans) == 13*2, len(resolution_scans)

    # Every necessary discovery rejects absent and duplicate sites, including a
    # changed/occupied entry, before any hook or native call is installed.
    discovery = [(p, matches[p]) for p, start, _ in resolution_scans if start is None]
    negatives = 0
    for pattern, address in discovery:
        saved = image[address-base]
        image[address-base] = 0xcc
        try:
            resolver.resolve(g.api, g.ffi)
        except Exception as error:
            assert 'native context not found' in str(error), str(error)
            negatives += 1
        else:
            raise AssertionError('accepted occupied '+pattern)
        image[address-base] = saved
        # Force the bounded second scan to report a duplicate, while the first
        # scan and all bytes still come from the real image.
        def duplicate(p, start=None, stop=None):
            return address+0x1000 if p == pattern and start else scan(p, start, stop)
        g.core.scanForAOB = duplicate
        try:
            resolver.resolve(g.api, g.ffi)
        except Exception as error:
            assert 'ambiguous' in str(error), str(error)
            negatives += 1
        else:
            raise AssertionError('accepted ambiguous '+pattern)
        g.core.scanForAOB = scan

    for name in ('menuConstructor','modalConstructor','activateModal','text','border','basicButton'):
        address = sites[name].address
        saved = image[address-base]
        image[address-base] = 0xe9
        try:
            resolver.resolve(g.api, g.ffi)
        except Exception as error:
            assert 'Recorder UI '+name+': modified native context' in str(error), str(error)
            negatives += 1
        else:
            raise AssertionError('accepted occupied owner '+name)
        image[address-base] = saved
    for address in (sites.missionBar.address+18, sites.mapViewport.address+2):
        saved = read(address, 4)
        image[address-base:address-base+4] = struct.pack('<I', 123)
        try:
            resolver.resolve(g.api, g.ffi)
        except Exception as error:
            assert 'operands disagree' in str(error) or 'layout differs' in str(error), str(error)
            negatives += 1
        else:
            raise AssertionError('accepted incoherent data operands')
        image[address-base:address-base+4] = saved
    return {'variant':variant,'referenceSha256':hashlib.sha256(raw).hexdigest(),
            'uiSourceSha256':hashlib.sha256(ui_game.read_bytes()).hexdigest(),
            'bindings':len(list(sites.items())), 'frameworkScans':len(resolution_scans),
            'negativeCases':negatives, 'scope':'Private image/component test; no installed game.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--variant', choices=['SHC','Extreme'], required=True)
    p.add_argument('--ui-game', type=Path, required=True)
    p.add_argument('--framework-code', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = check(a.reference,a.variant,a.ui_game,a.framework_code)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
