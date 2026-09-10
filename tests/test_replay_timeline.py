import unittest
from pathlib import Path
from lupa.luajit21 import LuaRuntime


class ReplayTimelineTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().root=Path(__file__).resolve().parents[1].as_posix()
        self.lua.execute("package.path=root..'/?.lua;'..package.path")

    def test_recovery_clock_reset_uses_elapsed_segment_lengths(self):
        self.lua.execute('''
local first={id='a',startTick=100,lastTick=400,nextReplay='b'}
local second={id='b',startTick=200,lastTick=900}
local t=require('code/replay-timeline').new(first,{b={manifest=second}})
assert(t.total==1000)
local id,tick=t:at(0); assert(id=='a' and tick==100)
id,tick=t:at(.3); assert(id=='b' and tick==200)
id,tick=t:at(1); assert(id=='b' and tick==900)
local position,total=t:position('b',500); assert(position==600 and total==1000)
assert(not pcall(function() t:at(0/0) end))
assert(not pcall(function() t:at(1.1) end))
''')

    def test_empty_and_incomplete_segments_have_finite_positions(self):
        self.lua.execute('''
local first={id='a',startTick=100,lastTick=100,nextReplay='missing'}
local t=require('code/replay-timeline').new(first,{incomplete={after='a'}})
local id,tick=t:at(1); assert(id=='a' and tick==100 and t.total==0)
assert(t:position('a',999)==0 and t:position('a',0)==0)
first.nextReplay='a'
assert(not pcall(require('code/replay-timeline').new,first,{a={manifest=first}}))
''')
