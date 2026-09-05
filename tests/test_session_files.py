"""Exercise actual Lua file I/O and JSON on a temporary replay directory."""
from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest

from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class SessionFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        lua = self.lua

        def from_lua(value):
            if hasattr(value, 'items'):
                keys = list(value.keys())
                if keys and all(isinstance(k, int) for k in keys):
                    return [from_lua(value[i]) for i in range(1, len(keys)+1)]
                return {k: from_lua(v) for k, v in value.items()}
            return value

        def mkdir(path):
            try:
                Path(path).mkdir()
                return True
            except FileExistsError:
                return False

        g = lua.globals()
        g.source_root = ROOT.as_posix()
        g.temp_root = self.root.as_posix()
        g.encode_json = lambda value: json.dumps(from_lua(value), separators=(',', ':'))
        g.decode_json = lambda value: lua.table_from(json.loads(value), recursive=True)
        g.hash_string = lambda value: hashlib.sha256(value.encode()).hexdigest()
        g.make_directory = mkdir
        g.replace_file = os.replace
        g.directories = lambda path: lua.table_from([str(p) for p in Path(path).iterdir() if p.is_dir()])
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
json={encode=function(_,v) return encode_json(v) end,decode=function(_,v) return decode_json(v) end}
sha={sha256=hash_string}
package.loaded['code/platform']={mkdir=make_directory,replace=replace_file}
ucp={internal={io={directories=directories}}}
store=require('code/sessions'); store.ROOT=temp_root..'/replays'
CONFIG_FILE=temp_root..'/current.yml'
store.write(CONFIG_FILE,'load-order: [recorder-0.3.0]\\n')
profile={name='SHC',sha256=string.rep('a',64)}
function recording()
 local m=store.new(profile)
 m.player=1; m.startTick=0; m.lastTick=64; m.finalRng={11,22,3,4}
 m.snapshotHash=string.rep('b',64); m.rngHash=string.rep('c',64)
 local path=store.path(m.id)
 local function command(t) return {commandCategory=28,player=1,time=t,size=1,data='01'} end
 store.write(path..'/stream-commands.json',json:encode(command(10))..'\\n'..json:encode(command(65))..'\\n')
 store.write(path..'/stream-rng-sync.json',json:encode({time=0,rng={1,2,3,4}})..'\\n'..json:encode({time=64,rng=m.finalRng})..'\\n')
 store.write(path..'/stream-infself.json',json:encode({gameType=0,mapSeed=123,matchSeed=123,RNGvalue1=1,RNGvalue2=2,RNGindex1=4,RNGindex2=3})..'\\n')
 return m
end
''')

    def test_real_roundtrip_trims_only_commands_after_end_and_checks_settings(self):
        self.lua.execute('''
local m=recording(); store.finish(m)
assert(m.commandCount==1 and m.status=='complete')
local loaded=store.load(m.id,profile); store.preflight(loaded)
assert(store.compatible(loaded))
store.write(CONFIG_FILE,'changed settings')
assert(not store.compatible(loaded))
assert(store.list()[1].id==m.id)
''')

    def test_repeated_recordings_never_overwrite_existing_files(self):
        self.lua.execute('''
local a=recording(); store.finish(a)
local before=store.read(store.path(a.id)..'/manifest.json')
local b=recording(); assert(a.id~=b.id)
assert(store.read(store.path(a.id)..'/manifest.json')==before)
''')

    def test_modified_stream_and_settings_are_rejected(self):
        self.lua.execute('''
local m=recording(); store.finish(m)
store.write(store.path(m.id)..'/stream-commands.json','')
assert(not pcall(store.preflight,m))
store.write(store.path(m.id)..'/ucp-config.yml','modified')
assert(not pcall(store.load,m.id,profile))
''')

    def test_incomplete_checkpoint_stream_is_not_marked_complete(self):
        self.lua.execute('''
local m=recording()
store.write(store.path(m.id)..'/stream-rng-sync.json','')
assert(not pcall(store.finish,m))
local disk=json:decode(store.read(store.path(m.id)..'/manifest.json'))
assert(disk.status~='complete')
''')

    def test_out_of_order_commands_are_rejected_before_completion(self):
        self.lua.execute('''
local m=recording()
local path=store.path(m.id)..'/stream-commands.json'
local first,second=store.read(path):match('([^\\n]+)\\n([^\\n]+)')
store.write(path,second..'\\n'..first..'\\n')
assert(not pcall(store.finish,m)); assert(m.status~='complete')
''')

    def test_invalid_manifest_and_path_do_not_load(self):
        self.lua.execute('''
for _,id in ipairs({'../outside','a/b','a\\\\b','',string.rep('x',80)}) do
 assert(not pcall(store.path,id))
end
local m=recording(); store.finish(m)
m.lastTick=-1; store.save(m)
assert(not pcall(store.load,m.id,profile))
''')
