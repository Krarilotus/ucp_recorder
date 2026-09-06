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
    def test_named_copies_are_independent_complete_files_and_do_not_trim_source(self):
        self.lua.execute('''
local m=recording(); local path=store.path(m.id)
store.write(path..'/start.sav','snapshot'); store.write(path..'/rng.bin','rng')
m.snapshotHash=sha.sha256('snapshot'); m.rngHash=sha.sha256('rng')
local original=store.read(path..'/stream-commands.json')
local a=store.copy(m,'Stream match',m.finalRngHash)
local b=store.copy(m,'Stream match',m.finalRngHash)
assert(a.id~=b.id and a.id~=m.id and a.status=='complete' and a.commandCount==1)
assert(a.displayName=='Stream match' and a.sourceId==m.id)
assert(m.commandCount==0 and m.status=='armed' and store.read(path..'/stream-commands.json')==original)
store.preflight(store.load(a.id,profile)); store.preflight(store.load(b.id,profile))
local sealed=store.read(store.path(a.id)..'/stream-commands.json')
store.rename(a.id,'Renamed',profile)
assert(store.load(a.id,profile).displayName=='Renamed')
assert(store.read(store.path(a.id)..'/stream-commands.json')==sealed)
''')

    def test_naming_rejects_controls_and_never_uses_name_as_path(self):
        self.lua.execute('''
local m=recording(); store.finish(m)
for _,name in ipairs({'','   ',string.rep('x',41),'bad\\nname','bad\\0name'}) do
 assert(not pcall(store.rename,m.id,name,profile))
end
local renamed=store.rename(m.id,' ../same/name ',profile)
assert(renamed.id==m.id and renamed.displayName=='../same/name')
assert(store.load(m.id,profile).displayName=='../same/name')
''')

    def test_failed_copy_cannot_be_played_and_preserves_source(self):
        self.lua.execute('''
local m=recording(); local before=store.read(store.path(m.id)..'/stream-commands.json')
assert(not pcall(store.copy,m,'Missing snapshot',m.finalRngHash))
assert(store.read(store.path(m.id)..'/stream-commands.json')==before)
for _,item in ipairs(store.list()) do
 if item.id~=m.id then assert(item.status=='failed' and not pcall(store.load,item.id,profile)) end
end
''')
    def test_oversized_same_tick_batch_cannot_be_sealed_or_loaded(self):
        self.lua.execute('''
local m=recording(); local path=store.path(m.id)..'/stream-commands.json'
local line=store.read(path):match('[^\\n]+')..'\\n'
store.write(path,string.rep(line,101))
assert(not pcall(store.finish,m) and m.status~='complete')
store.write(path,string.rep(line,100)); store.finish(m); store.preflight(m)
assert(m.commandCount==100)
''')

    def test_missing_full_rng_evidence_prevents_completion(self):
        self.lua.execute('''
local m=recording(); m.finalRngHash=nil
assert(not pcall(store.finish,m))
m=recording()
local path=store.path(m.id)..'/stream-rng-sync.json'
local lines={}
for line in store.read(path):gmatch('[^\\n]+') do
 local row=json:decode(line); row.rngHash=nil; lines[#lines+1]=json:encode(row)
end
store.write(path,table.concat(lines,'\\n')..'\\n')
assert(not pcall(store.finish,m))
''')

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
function resourceState(value) local t={}; for i=1,200 do t[i]=value or 0 end; return t end
function recording()
 local m=store.new(profile)
 m.player=1; m.startTick=0; m.lastTick=64; m.finalRng={11,22,3,4}
 m.startResources=resourceState(); m.finalResources=resourceState()
 m.snapshotHash=string.rep('b',64); m.rngHash=string.rep('c',64); m.finalRngHash=string.rep('d',64)
 local path=store.path(m.id)
 local function command(t) return {commandCategory=28,player=1,time=t,size=1,data='01'} end
 store.write(path..'/stream-commands.json',json:encode(command(10))..'\\n'..json:encode(command(65))..'\\n')
 store.write(path..'/stream-rng-sync.json',json:encode({time=0,rng={1,2,3,4},resources=resourceState(),rngHash=m.rngHash})..'\\n'..json:encode({time=64,rng=m.finalRng,resources=resourceState(),rngHash=m.finalRngHash})..'\\n')
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

    def test_missing_or_malformed_resource_evidence_prevents_completion(self):
        self.lua.execute('''
local m=recording(); m.finalResources[200]=nil
assert(not pcall(store.finish,m))
m=recording()
local path=store.path(m.id)..'/stream-rng-sync.json'
store.write(path,json:encode({time=0,rng={1,2,3,4}})..'\\n')
assert(not pcall(store.finish,m))
local validation=require('code/validation')
for _,invalid in ipairs({1.5,2147483648,-2147483649}) do
 local values=resourceState(); values[100]=invalid
 assert(not pcall(validation.resources,values))
end
''')
