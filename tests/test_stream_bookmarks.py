import unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime


class StreamBookmarkTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root=Path(__file__).resolve().parents[1].as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path")

    def test_real_file_positions_preserve_prefetched_events_on_repeat_restore(self):
        self.lua.execute('''
local Streams=require('code/replay-streams')
local r=Streams:new({name='test'}); r.mode='play'
local f=assert(io.tmpfile()); r.commandsFile=f
assert(f:write('first\\r\\nsecond\\r\\nthird\\r\\n')); assert(f:seek('set',0))
local first=f:read('*l'); r.nextCommand={time=10,data=first}
r.nextWork={time=10,count=2}; r.workEnded=false
local bookmark=r:bookmark()
local second=f:read('*l'); local third=f:read('*l')
for i=1,3 do
 r.nextCommand=nil; r.nextWork=nil; r.workEnded=true
 r:restoreBookmark(bookmark)
 assert(r.nextCommand.time==10 and r.nextCommand.data==first)
 assert(r.nextWork.count==2 and r.workEnded==false)
 assert(f:read('*l')==second and f:read('*l')==third and f:read('*l')==nil)
end
r:closeFiles()
''')

    def test_incomplete_invalid_or_foreign_positions_fail_before_moving_files(self):
        self.lua.execute('''
local r=require('code/replay-streams'):new({name='test'}); r.mode='play'
local moved=0
r.commandsFile={seek=function() moved=moved+1; return 0 end}
for _,positions in ipairs({{}, {commandsFile=-1}, {commandsFile=0/0},
 {commandsFile=0,foreign=0}, {commandsFile=0,phaseFile=0}}) do
 assert(not pcall(function() r:restoreBookmark({positions=positions}) end))
 assert(moved==0)
end
''')
