import unittest
import test_recorder as fixture


class PauseTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def test_explicit_and_native_menu_pause_are_both_reported_without_writes(self):
        self.check('''
local Engine=require('code/engine')
local modal=0
local e=setmetatable({sites={paused=100,gameCore=200},haltingMenuNative=function(this)
 assert(this==200); return modal end},{__index=Engine})
memory[100]=0; assert(not e:isPaused())
modal=1; assert(e:isPaused() and memory[100]==0)
modal=0; memory[100]=1; assert(e:isPaused() and memory[100]==1)
''')
