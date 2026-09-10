import hashlib
from pathlib import Path
import tempfile
import unittest
from lupa.luajit21 import LuaRuntime


class SnapshotStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        g=self.lua.globals()
        g.root=Path(__file__).resolve().parents[1].as_posix()
        g.folder=self.path.as_posix()
        g.hash_string=lambda value:hashlib.sha256(value.encode('latin-1')).hexdigest()
        def hash_file(path,limit,chunk=None,progress=None):
            data=Path(path).read_bytes()
            assert len(data)<=limit
            if progress:progress(len(data))
            return hashlib.sha256(data).hexdigest()
        g.hash_file=hash_file
        g.mkdir=lambda path:Path(path).mkdir(parents=True,exist_ok=True)
        g.replace=lambda source,target:Path(source).replace(target)
        self.lua.execute('''
package.path=root..'/?.lua;'..package.path
local function write(path,data)
 local f=assert(io.open(path,'wb')); assert(f:write(data)); assert(f:close())
end
package.loaded['code/native-hash']={sha256=hash_string,file=hash_file}
package.loaded['code/platform']={mkdir=mkdir,replace=replace,milliseconds=function() return 0 end}
package.loaded['code/sessions']={write=write,path=function(id) return folder..'/'..id end}
snapshot=require('code/snapshot-store')
random=string.rep('x',0x9c50); resources=string.rep('r',800); tick=100
engine={tick=function() return tick end,rngData=function() return random end,
 resourceData=function() return resources end,commandsPending=function() return false end,
 saveSnapshot=function(_,path) write(path,string.rep('w',2000)) end}
manifest={id='recording',startTick=1,lastTick=500,commandCount=4}
r={engine=engine,mode='record',manifest=manifest,
 bookmark=function() return {positions={commandsFile=0,rngFile=0,infoFile=0}} end}
mkdir(folder..'/recording')
for _,file in ipairs({'stream-commands.json','stream-rng-sync.json','stream-infself.json'}) do
 write(folder..'/recording/'..file,'data\\n')
end
path=folder..'/point'
''')

    def test_capture_and_prepare_verify_files_and_leave_world_unchanged(self):
        self.lua.execute('''
point=assert(snapshot.capture(engine,path,12000,4,r:bookmark()))
assert(point.bytes==2000 and point.commands==4 and point.tick==100)
local ready=snapshot.prepare(manifest,point,path)
assert(ready.rng==random and ready.snapshotPath==path..'.sav')
assert(engine:tick()==100 and engine:resourceData()==resources)
snapshot.remove(path)
assert(not io.open(path..'.sav','rb') and not io.open(path..'.rng','rb'))
''')

    def test_corrupt_world_oversized_rng_and_bad_stream_offset_are_rejected(self):
        self.lua.execute('point=assert(snapshot.capture(engine,path,12000,4,r:bookmark()))')
        world=self.path/'point.sav'; original=world.read_bytes()
        world.write_bytes(b'z'+original[1:])
        self.lua.execute('assert(not pcall(snapshot.prepare,manifest,point,path))')
        world.write_bytes(original)
        rng=self.path/'point.rng'; random=rng.read_bytes(); rng.write_bytes(random+b'x')
        self.lua.execute('assert(not pcall(snapshot.prepare,manifest,point,path))')
        rng.write_bytes(random)
        self.lua.execute('''
point.bookmark.positions.commandsFile=999
assert(not pcall(snapshot.prepare,manifest,point,path))
''')

    def test_write_failure_cleans_partial_files_without_invalidating_original_replay(self):
        self.lua.execute('''
local replace=require('code/platform').replace
require('code/platform').replace=function(from,to)
 if to:match('%.rng$') then error('disk failure') end
 return replace(from,to)
end
local point,reason=snapshot.capture(engine,path,12000,4,r:bookmark())
assert(not point and reason:find('disk failure',1,true))
assert(not io.open(path..'.sav','rb') and not io.open(path..'.rng.tmp','rb'))
assert(manifest.commandCount==4 and engine:tick()==100)
''')

    def test_world_mutation_is_not_hidden_as_an_optional_cache_failure(self):
        self.lua.execute('''
local save=engine.saveSnapshot
engine.saveSnapshot=function(...) save(...); tick=tick+1 end
local ok,reason=pcall(snapshot.capture,engine,path,12000,4,r:bookmark())
assert(not ok and reason:find('changed simulation state',1,true))
assert(not io.open(path..'.sav','rb'))
''')

    def test_missing_optional_restore_point_does_not_prevent_named_replay_copy(self):
        self.lua.execute('''
point=assert(snapshot.capture(engine,path,12000,4,r:bookmark()))
manifest.snapshots={point}
local target={id='copy',startTick=1,lastTick=500,commandCount=4}
-- The capture is deliberately not in the embedded source directory.
snapshot.copy(manifest,target)
assert(not target.snapshots and manifest.snapshots[1]==point)
assert(io.open(path..'.sav','rb')):close()
''')
