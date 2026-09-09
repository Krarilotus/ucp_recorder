"""Native directory/header framing with a deliberately fake compression codec.

This tests the container writer independently of PKWARE. The original-codec
checks separately exercise actual compressed bytes against both executables.
"""
import json
import hashlib
from pathlib import Path
import struct
import unittest
import zlib

import test_world_capture as fixture


class WorldContainerTests(unittest.TestCase):
    setUp=fixture.WorldCaptureTests.setUp
    capture=fixture.WorldCaptureTests.capture

    def prepare(self):
        self.capture()
        virtual='ucp/multiplayer-recordings/'+self.root.name
        self.lua.globals().virtual_path=virtual
        def replace(source,target):
            def local(path): return self.root/str(path).removeprefix(virtual+'/')
            local(source).replace(local(target))
        self.lua.globals().replace_virtual=replace
        self.lua.globals().compress_fixture=lambda data:zlib.compress(data.encode('latin-1')).decode('latin-1')
        self.lua.execute('''
local original=io.open
io.open=function(path,mode)
 if path:sub(1,#virtual_path)==virtual_path then path=test_path..path:sub(#virtual_path+1) end
 return original(path,mode)
end
core.readInteger=function() return 20 end
engine.sites={gameCore=0x1fe7d10}; engine.singlePlayer=function() return true end
require('code/platform').replace=replace_virtual
require('code/native-hash').file=function(path,limit,onChunk)
 local data=require('code/world-reader').read(path,limit)
 if onChunk then onChunk(data,#data) end
 return sha.sha256(data)
end
compressions=0
package.loaded['code/world-codec']={withBuffers=function(capacity,callback)
 compressions=compressions+1
 return callback({compress=function(_,data)
  if #data==1000 or #data==40512 then return compress_fixture(data) end
 end})
end}
container=require('code/world-container')
''')

    def test_directory_and_metadata_preserve_captured_bytes(self):
        self.prepare()
        self.lua.execute('prepared=container.prepare(virtual_path,engine)')
        data=(self.root/'world-native.sav').read_bytes()
        marker=struct.unpack_from('<I',data)[0]; self.assertEqual(marker,0xffffffff)
        offset=4; blocks=[]
        while True:
            size=struct.unpack_from('<I',data,offset)[0]; offset+=4
            if not size: break
            blocks.append(data[offset:offset+size]); offset+=size
        self.assertEqual(len(blocks),6)
        self.assertEqual(zlib.decompress(blocks[0]),bytes(40512))
        self.assertEqual(blocks[1][:8]+zlib.decompress(blocks[1][8:]),b'h'*1008)
        self.assertEqual([len(b) for b in blocks[2:]],[8,28,1017,80])
        directory=data[offset:offset+3036]; payload=data[offset+3036:]
        self.assertEqual(struct.unpack_from('<4I',directory),(3036,len(self.expected),122,172))
        self.assertEqual(payload,self.expected)
        entries=json.loads((self.root/'world.json').read_text())['sections']
        for i,entry in enumerate(entries):
            values=[struct.unpack_from('<I',directory,32+array*600+i*4)[0] for array in range(5)]
            self.assertEqual(values,[entry['size'],entry['size'],entry['section'],0,entry['offset']])
        metadata=json.loads((self.root/'world-native.json').read_text())
        self.assertFalse(metadata['playable']); self.assertEqual(metadata['sections'],122)
        self.assertEqual(metadata['bytes'],len(data))

    def test_payload_limit_preserves_previous_prepared_file(self):
        self.prepare(); target=self.root/'world-native.sav'; target.write_bytes(b'previous')
        self.lua.execute('container.MAX_PAYLOAD=50')
        with self.assertRaisesRegex(Exception,'loader buffer'):
            self.lua.execute('container.prepare(virtual_path,engine)')
        self.assertEqual(target.read_bytes(),b'previous')
        self.assertFalse((self.root/'world-native.json').exists())

    def test_history_preparation_yields_and_matches_skirmish_container(self):
        self.prepare()
        self.lua.execute('container.prepare(virtual_path,engine)')
        expected=(self.root/'world-native.sav').read_bytes()
        self.lua.execute('''
core.readInteger=function() return 58 end
local progress=0
container.prepare(virtual_path,engine,function() progress=progress+1 end)
assert(progress==122)
''')
        self.assertEqual((self.root/'world-native.sav').read_bytes(),expected)

    def test_corrupt_section_is_never_published(self):
        self.prepare(); (self.root/'world.bin').write_bytes(b'x'*len(self.expected))
        with self.assertRaisesRegex(Exception,'section is damaged'):
            self.lua.execute('container.prepare(virtual_path,engine)')
        self.assertFalse((self.root/'world-native.sav').exists())

    def test_cache_avoids_recompression_and_still_checks_source_bytes(self):
        self.prepare()
        self.lua.execute('container.prepare(virtual_path,engine); container.prepare(virtual_path,engine); assert(compressions==1)')
        (self.root/'world.bin').write_bytes(b'x'*len(self.expected))
        with self.assertRaisesRegex(Exception,'section is damaged'):
            self.lua.execute('container.prepare(virtual_path,engine)')

    def test_corrupt_cache_or_old_converter_rebuilds_from_original(self):
        self.prepare()
        self.lua.execute('container.prepare(virtual_path,engine)')
        expected=(self.root/'world-native.sav').read_bytes()
        (self.root/'world-native.sav').write_bytes(b'corrupt')
        self.lua.execute('container.prepare(virtual_path,engine); assert(compressions==2)')
        self.assertEqual((self.root/'world-native.sav').read_bytes(),expected)
        self.lua.execute("require('code/world-cache').REVISION=2; container.prepare(virtual_path,engine); assert(compressions==3)")

    def test_supplied_cache_metadata_cannot_authorize_different_native_bytes(self):
        self.prepare()
        self.lua.execute('container.prepare(virtual_path,engine)')
        expected=(self.root/'world-native.sav').read_bytes()
        forged=b'x'*len(expected)
        (self.root/'world-native.sav').write_bytes(forged)
        metadata=json.loads((self.root/'world-native.json').read_text())
        metadata['sha256']=hashlib.sha256(forged).hexdigest()
        (self.root/'world-native.json').write_text(json.dumps(metadata))
        # A new process has no proof about supplied derivative files, even when
        # their metadata correctly names the genuine source and forged digest.
        self.lua.execute("package.loaded['code/world-cache']=nil; container.prepare(virtual_path,engine); assert(compressions==2)")
        self.assertEqual((self.root/'world-native.sav').read_bytes(),expected)

    def test_returned_metadata_does_not_mutate_the_cached_proof(self):
        self.prepare()
        self.lua.execute('''
local result=container.prepare(virtual_path,engine)
result.sha256=string.rep('0',64)
result=container.prepare(virtual_path,engine)
assert(result.sha256~=string.rep('0',64) and compressions==1)
result.sha256=string.rep('1',64)
assert(container.prepare(virtual_path,engine).sha256~=string.rep('1',64))
''')

    def test_conversion_does_not_run_during_a_match_or_with_a_traversal_path(self):
        self.prepare()
        self.lua.execute('core.readInteger=function() return 14 end')
        with self.assertRaisesRegex(Exception,'Skirmish or battle history'):
            self.lua.execute('container.prepare(virtual_path,engine)')
        self.lua.execute('core.readInteger=function() return 20 end')
        with self.assertRaisesRegex(Exception,'capture path'):
            self.lua.execute("container.prepare('ucp/multiplayer-recordings/../test',engine)")
        self.assertFalse((self.root/'world-native.sav.tmp').exists())
