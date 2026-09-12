"""Schema admission remains strict while native descriptor addresses may move."""
import hashlib
from pathlib import Path
import struct
import unittest
from lupa.lua54 import LuaRuntime as Lua54
from lupa.luajit21 import LuaRuntime as LuaJIT

ROOT=Path(__file__).resolve().parents[1]


class WorldLayoutTests(unittest.TestCase):
    def fixture(self,runtime,variant):
        lua=runtime(unpack_returned_tuples=True,encoding='latin-1')
        g=lua.globals(); g.source_root=ROOT.as_posix()
        g.hash_data=lambda data:hashlib.sha256(data.encode('latin-1')).hexdigest()
        lua.execute("package.path=source_root..'/?.lua;'..package.path; sha={sha256=hash_data}")
        schema=lua.eval("(require('code/world-sections'))")[variant]
        rows=[]; address=0x10000000
        for entry in schema.entries.values():
            rows.append(struct.pack('<IIIHH',address,0,entry.size,entry.compressed,entry.section))
            address+=entry.size+64
        raw=b''.join(rows)+bytes(16)
        return lua,raw,lua.eval("require('code/world-layout').decode")

    def test_relocated_addresses_keep_schema_and_actual_integrity_hash(self):
        for runtime in (Lua54,LuaJIT):
            for variant in ('SHC','Extreme'):
                with self.subTest(runtime=runtime,variant=variant):
                    _,raw,decode=self.fixture(runtime,variant)
                    entries,profile=decode(raw,variant)
                    self.assertEqual(len(entries),122)
                    self.assertEqual(entries[1].address,0x10000000)
                    self.assertEqual(profile.hash,hashlib.sha256(raw).hexdigest())
                    self.assertEqual(profile.total,13776465 if variant=='SHC' else 25168385)
                    moved=bytearray(raw)
                    for i in range(122): struct.pack_into('<I',moved,i*16,struct.unpack_from('<I',raw,i*16)[0]+0x1000000)
                    second,identity=decode(bytes(moved),variant)
                    self.assertEqual(second[1].address,entries[1].address+0x1000000)
                    self.assertNotEqual(identity.hash,profile.hash)
                    self.assertEqual(identity.total,profile.total)

    def test_every_descriptor_field_and_terminator_are_checked(self):
        for runtime in (Lua54,LuaJIT):
            for variant in ('SHC','Extreme'):
                _,raw,decode=self.fixture(runtime,variant)
                for row in range(122):
                    for offset,fmt in ((0,'I'),(4,'I'),(8,'I'),(12,'H'),(14,'H')):
                        changed=bytearray(raw)
                        position=row*16+offset
                        value=0 if offset==0 else struct.unpack_from('<'+fmt,raw,position)[0]+1
                        struct.pack_into('<'+fmt,changed,position,value)
                        with self.subTest(runtime=runtime,variant=variant,row=row,field=offset):
                            with self.assertRaises(Exception): decode(bytes(changed),variant)
                for i in range(16):
                    changed=bytearray(raw); changed[-16+i]=1
                    with self.assertRaisesRegex(Exception,'ending'): decode(bytes(changed),variant)
                with self.assertRaises(Exception): decode(raw[:-1],variant)
                with self.assertRaises(Exception): decode(raw,'unknown')
