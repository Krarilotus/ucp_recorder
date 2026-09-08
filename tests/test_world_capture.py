"""Binary Lua I/O, exact section copies, failure isolation and offline inspection."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from lupa.luajit21 import LuaRuntime
from test_multiplayer_capture import inspector

ROOT = Path(__file__).resolve().parents[1]


class WorldCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lua = LuaRuntime(encoding='latin-1', unpack_returned_tuples=True)
        self.memory = {}
        self.reads = []
        rows = []
        for i in range(122):
            size = 70001 if i == 0 else 13
            address = 0x1000000 + i * 0x20000
            rows.append(struct.pack('<IIIHH', address, 0, size, 1, 1001+i))
            self.memory[address] = bytes((j+i) % 256 for j in range(size))
        self.table = b''.join(rows)+bytes(16)
        self.memory[0xb92a58] = self.table
        self.digest = hashlib.sha256(self.table).hexdigest()
        self.total = sum(len(v) for a,v in self.memory.items() if a != 0xb92a58)
        self.expected = b''.join(self.memory[a] for a in sorted(self.memory) if a != 0xb92a58)
        g = self.lua.globals()

        def convert(value):
            if hasattr(value, 'items'):
                keys = list(value.keys())
                if keys and all(isinstance(k, int) for k in keys):
                    return [convert(value[i]) for i in range(1, len(keys)+1)]
                return {k: convert(v) for k,v in value.items()}
            return value

        def read(address, size):
            self.reads.append((address,size))
            for start,data in self.memory.items():
                if start <= address and address+size <= start+len(data):
                    return data[address-start:address-start+size].decode('latin-1')
            raise ValueError(f'Unexpected memory read {address:x}+{size}')

        def mkdir(path):
            try:
                Path(path).mkdir()
                return True
            except FileExistsError:
                return False

        g.source_root = ROOT.as_posix()
        g.test_path = self.root.as_posix()
        g.read_memory = read
        g.encode_json = lambda v: json.dumps(convert(v),separators=(',', ':'))
        g.decode_json = lambda v: self.lua.table_from(json.loads(v),recursive=True)
        g.hash_string = lambda v: hashlib.sha256(v.encode('latin-1')).hexdigest()
        g.replace_file = os.replace
        g.make_directory = mkdir
        g.table_hash = self.digest
        g.total_bytes = self.total
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
json={encode=function(_,v) return encode_json(v) end,decode=function(_,v) return decode_json(v) end}
sha={sha256=hash_string}; core={readString=read_memory}
package.loaded['code/native-hash']={prepare=function() end,sha256=hash_string}
package.loaded['code/platform']={replace=replace_file,mkdir=make_directory}
require('code/native').profile={name='SHC',sha256=string.rep('a',64)}
local profile=require('code/world-sections').SHC
profile.hash=table_hash; profile.total=total_bytes
store=require('code/sessions'); files=require('code/capture-files')
world=require('code/world-capture'); now=1
require('code/world-header').read=function()
 local data=string.rep('h',2141)
 return data,{format=1,bytes=2141,sha256=sha.sha256(data),fields={
  {name='description',offset=0,size=1008},{name='timeAndHash',offset=1008,size=8},
  {name='players',offset=1016,size=28},{name='scenario',offset=1044,size=1017},
  {name='skirmish',offset=2061,size=80}}}
end
engine={tick=function() return now end,networkState=function() return {mode=1} end,
 rngData=function() return string.rep('a',64) end,resourceState=function() return {} end}
settings={raw='settings',environment='environment',hash=sha.sha256('settings'),
 environmentHash=sha.sha256('environment')}
''')
        mapping = patch.dict(inspector.WORLD_TABLES, {'SHC': (self.digest, self.total)})
        mapping.start()
        self.addCleanup(mapping.stop)

    def capture(self):
        self.lua.execute('capture=files.begin(test_path,engine,settings)')
        return json.loads((self.root/'capture.json').read_text())

    def test_exact_binary_sections_and_copy_never_call_native_writes(self):
        capture = self.capture()
        self.assertEqual(capture['world']['status'], 'complete')
        self.assertEqual((self.root/'world.bin').read_bytes(), self.expected)
        self.assertEqual((self.root/'world-layout.bin').read_bytes(), self.table)
        self.assertTrue(all(size <= 65536 for _,size in self.reads))
        evidence = inspector.world_capture(self.root)
        self.assertEqual(len(evidence['sections']),122)
        self.lua.execute('''
store.write(test_path..'/commands.jsonl','a flushed journal prefix')
copy=files.copy(capture,'name',24,0,0,1)
''')
        copied = Path(self.lua.eval('copy.path'))
        self.addCleanup(lambda: __import__('shutil').rmtree(copied))
        self.assertEqual((copied/'world.bin').read_bytes(), self.expected)
        self.assertEqual((copied/'world-header.bin').read_bytes(),b'h'*2141)
        self.assertEqual(inspector.compare_worlds(self.root, copied)['differences'], [])

    def test_corrupt_descriptor_rejected_before_dereferencing_world(self):
        self.memory[0xb92a58] = bytes(1968)
        capture = self.capture()
        self.assertEqual(capture['world']['status'],'failed')
        self.assertEqual(self.reads, [(0xb92a58,1968)])
        self.assertFalse((self.root/'world.bin').exists())
        self.assertTrue((self.root/'initial-rng.bin').exists())

    def test_partial_world_does_not_prevent_command_capture_setup(self):
        del self.memory[0x1020000]
        capture = self.capture()
        self.assertEqual(capture['status'],'recording')
        self.assertEqual(capture['world']['status'],'failed')
        self.assertEqual((self.root/'world.bin').stat().st_size,70001)
        self.assertEqual(inspector.world_capture(self.root)['status'],'unavailable')

    def test_automarket_exact_state_including_credit_fees_and_local_slot(self):
        market = struct.pack('<I',2)+bytes(i%256 for i in range(2412))
        self.memory[0x5000000] = market
        self.lua.execute('''
allActiveExtensions={{name='automarket',version='1.1.0'},
 {name='protocol',version='1.0.0'},{name='map-extensions',version='1.0.0'}}
modules={automarket={pAutomarketData=0x5000000},
 protocol={getProtocolNumber=function() return 130 end}}
''')
        capture = self.capture()
        self.assertTrue(capture['world']['automarket'])
        self.assertEqual((self.root/'automarket.bin').read_bytes(),market)
        self.assertEqual(inspector.world_capture(self.root)['automarket']['bytes'],2416)
        (self.root/'automarket.bin').write_bytes(market[:-1])
        with self.assertRaisesRegex(ValueError,'Automarket'):
            inspector.world_capture(self.root)

    def test_tampered_world_section_layout_and_manifest_are_detected(self):
        self.capture()
        path = self.root/'world.bin'
        data = path.read_bytes()
        path.write_bytes(b'x'+data[1:])
        with self.assertRaisesRegex(ValueError,'section 1001'):
            inspector.world_capture(self.root)
        path.write_bytes(data)
        (self.root/'world-layout.bin').write_bytes(bytes(1968))
        with self.assertRaisesRegex(ValueError,'layout'):
            inspector.world_capture(self.root)
        (self.root/'world-layout.bin').write_bytes(self.table)
        (self.root/'world.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'manifest hash'):
            inspector.world_capture(self.root)

    def test_peer_comparison_locates_first_different_native_byte(self):
        self.capture()
        other = self.root/'peer'
        other.mkdir()
        self.lua.globals().peer_path = other.as_posix()
        data = self.memory[0x1000000]
        self.memory[0x1000000] = data[:66666]+b'X'+data[66667:]
        self.lua.execute('files.begin(peer_path,engine,settings)')
        result = inspector.compare_worlds(self.root,other)
        self.assertEqual(len(result['differences']),1)
        self.assertEqual(result['differences'][0]['firstAddress'],f'0x{0x1000000+66666:08X}')

    def test_tick_advance_is_not_a_complete_world(self):
        self.lua.execute('''
local original=core.readString
core.readString=function(address,size)
 local data=original(address,size)
 if address==0x1000000 then now=2 end
 return data
end
''')
        capture=self.capture()
        self.assertEqual(capture['world']['status'],'failed')
        self.assertIn('Simulation advanced',capture['world']['reason'])

    def test_short_read_preserves_evidence_but_rejects_world(self):
        self.lua.execute('''
local original=core.readString
core.readString=function(address,size)
 local data=original(address,size)
 if address==0x1000000 then return data:sub(2) end
 return data
end
''')
        capture=self.capture()
        self.assertEqual(capture['world']['status'],'failed')
        self.assertIn('Short native world read',capture['world']['reason'])

    def test_missing_or_changed_header_is_not_verified_evidence(self):
        self.capture()
        (self.root/'world-header.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'header'):
            inspector.world_capture(self.root)

    def test_old_world_capture_remains_inspectable_without_header(self):
        capture=self.capture()
        manifest=json.loads((self.root/'world.json').read_text())
        del manifest['header']; del capture['world']['header']
        raw=json.dumps(manifest).encode()
        (self.root/'world.json').write_bytes(raw)
        capture['world']['hash']=hashlib.sha256(raw).hexdigest()
        (self.root/'capture.json').write_text(json.dumps(capture))
        self.assertIsNone(inspector.world_capture(self.root)['header'])


if __name__ == '__main__':
    unittest.main()
