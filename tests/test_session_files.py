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
    def test_ai_only_spectator_can_seal_but_cannot_own_commands_or_mp(self):
        self.lua.execute('''
local m=recording(); local path=store.path(m.id)
m.player=0
store.write(path..'/stream-commands.json','')
store.write(path..'/start.sav','snapshot'); m.snapshotHash=sha.sha256('snapshot')
store.write(path..'/rng.bin','rng'); m.rngHash=sha.sha256('rng')
local copy=store.copy(m,'AI-only spectator',m.finalRngHash)
assert(copy.player==0 and copy.commandCount==0 and copy.status=='complete')
store.preflight(store.load(copy.id,profile))
store.finish(m); store.preflight(store.load(m.id,profile))
local validation=require('code/validation')
for slot=0,8 do
 local command={commandCategory=34,player=slot,time=10,size=1,data='01'}
 assert(not pcall(validation.sessionCommand,command,m))
end
m.commandCount=1; assert(not pcall(validation.manifest,m)); m.commandCount=0
m.multiplayer={}; assert(not pcall(validation.manifest,m)); m.multiplayer=nil
for _,slot in ipairs({-1,9,0.5}) do
 m.player=slot; assert(not pcall(validation.manifest,m))
end
''')

    def test_named_snapshot_and_sealing_never_read_whole_large_payloads(self):
        self.lua.execute('''
local m=recording(); local p=store.path(m.id)
local snapshot=string.rep('saved world',20000)
store.write(p..'/start.sav',snapshot); m.snapshotHash=sha.sha256(snapshot)
store.write(p..'/rng.bin','rng'); m.rngHash=sha.sha256('rng')
local original=store.read(p..'/stream-commands.json')
local oldOpen=io.open; local reads=0
io.open=function(path,mode)
 local f,err=oldOpen(path,mode); if not f then return f,err end
 if mode~='rb' or not (path:find('stream-',1,true) or path:find('start.sav',1,true)) then return f end
 return {read=function(_,n)
  assert(type(n)=='number' and n<=65536,'Unbounded replay payload read')
  reads=reads+1; return f:read(n)
 end,seek=function(_,...) return f:seek(...) end,lines=function() return f:lines() end,
 close=function() return f:close() end}
end
local copy=store.copy(m,'Bounded snapshot',m.finalRngHash)
store.finish(m)
io.open=oldOpen
assert(reads>4 and copy.status=='complete' and m.status=='complete')
assert(copy.commandCount==1 and m.commandCount==1)
assert(store.read(store.path(copy.id)..'/start.sav')==snapshot)
assert(store.read(p..'/start.sav')==snapshot)
assert(store.read(p..'/stream-commands.json')==original:match('[^\\n]+')..'\\n')
store.preflight(copy); store.preflight(m)
''')

    def test_stream_hash_read_failure_never_publishes_complete_manifest(self):
        self.lua.execute('''
local m=recording()
local digest=require('code/native-hash'); local original=digest.file
digest.file=function(path,...)
 if path:find('stream-rng-sync.json',1,true) then error('injected read failure') end
 return original(path,...)
end
assert(not pcall(store.finish,m))
local disk=json:decode(store.read(store.path(m.id)..'/manifest.json'))
assert(m.status~='complete' and disk.status~='complete')
digest.file=original; store.finish(m); store.preflight(m)
''')

    def test_preflight_splits_large_streams_and_rejects_damaged_tail_without_read_all(self):
        self.lua.execute('''
local m=recording(); local p=store.path(m.id)
m.lastTick=6400
local commands={}; for i=1,5000 do commands[i]=json:encode({commandCategory=34,player=1,time=i,size=1,data='01'}) end
store.write(p..'/stream-commands.json',table.concat(commands,'\\r\\n'))
local checkpoints={}; for tick=0,6400,64 do
 checkpoints[#checkpoints+1]=json:encode({time=tick,rng={1,2,3,4},resources=resourceState(),rngHash=m.rngHash})
end
store.write(p..'/stream-rng-sync.json',table.concat(checkpoints,'\\r\\n'))
m.commandCount=5000
for name,file in pairs({commands='stream-commands.json',checkpoints='stream-rng-sync.json',info='stream-infself.json'}) do
 m[name..'Hash']=sha.sha256(store.read(p..'/'..file))
end
local oldOpen=io.open; local closed=0
io.open=function(path,mode)
 local f=assert(oldOpen(path,mode))
 return {read=function(_,n) assert(type(n)=='number' and n<=65536); return f:read(n) end,
 close=function() closed=closed+1; return f:close() end}
end
local progress=0; store.preflight(m,function() progress=progress+1 end)
assert(progress>5000 and closed==3)
io.open=oldOpen
store.write(p..'/stream-commands.json',table.concat(commands,'\\n')..'\\n'..commands[1])
m.commandsHash=sha.sha256(store.read(p..'/stream-commands.json'))
local ok,reason=pcall(store.preflight,m)
assert(not ok and tostring(reason):find('ordered timeline',1,true))
''')

    def test_removal_preserves_files_and_prevents_reusing_archived_identity(self):
        def archive(root, identity):
            base=Path(root)
            destination=base/'removed'/identity
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():
                raise OSError('destination already exists')
            (base/identity).rename(destination)
        self.lua.globals().archive_directory=archive
        self.lua.execute('''
require('code/platform').removeReplay=archive_directory
local m=recording(); store.finish(m)
local p=store.path(m.id); local commands=store.read(p..'/stream-commands.json')
store.remove(m.id)
assert(#store.list()==0)
assert(store.read(store.ROOT..'/removed/'..m.id..'/stream-commands.json')==commands)
assert(not pcall(store.remove,'../escape'))
local active=recording(); assert(active.id~=m.id); active.status='recording'; store.save(active)
assert(not pcall(store.remove,active.id))
active.status='failed'; store.save(active); store.remove(active.id)
assert(#store.list()==0)
''')

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
        def hash_file(path, limit):
            self.assertLessEqual(Path(path).stat().st_size, limit)
            with open(path, 'rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()
        g.hash_file = hash_file
        g.make_directory = mkdir
        g.replace_file = os.replace
        g.directories = lambda path: lua.table_from([str(p) for p in Path(path).iterdir() if p.is_dir()])
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
json={encode=function(_,v) return encode_json(v) end,decode=function(_,v) return decode_json(v) end}
sha={sha256=hash_string}
-- Keep real Lua streaming/decoding; replace only the Windows hashing boundary.
package.loaded['code/native-hash']={file=function(path,limit,onChunk)
 if onChunk then
  local f=assert(io.open(path,'rb'))
  local ok,reason=pcall(function()
   while true do local chunk=f:read(65536); if not chunk then break end; onChunk(chunk) end
  end)
  assert(f:close()); assert(ok,reason)
 end
 return hash_file(path,limit)
end}
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
 local function command(t) return {commandCategory=34,player=1,time=t,size=1,data='01'} end
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
