import unittest
import test_recorder as fixture


class ReplayViewTests(unittest.TestCase):
    setUp=fixture.RecorderTests.setUp
    check=fixture.RecorderTests.check

    def setup_view(self):
        self.check('''
local roster={}; for i=1,8 do roster[i]={kind=i==4 and 'ai' or 'empty'} end
r={mode='play',active=true,status='playing',manifest={player=1},engine={
 singlePlayer=function() return not multiplayer end,
 networkState=function() return {roster=roster} end}}
view=require('code/replay-view').new(r)
memory[0x1a275dc]=1; memory[0x1a275d8]=7 -- native command actor is separate
''')

    def test_view_scope_restores_identity_after_nested_render_and_exception(self):
        self.setup_view()
        self.check('''
assert(#view:players()==2); view:select(4)
assert(memory[0x1a275dc]==1 and view:player()==4)
local result=view:render(function()
 assert(memory[0x1a275dc]==4 and memory[0x1a275d8]==7 and r.manifest.player==1)
 assert(view:render(function() return memory[0x1a275dc] end)==4)
 return 42
end)
assert(result==42 and memory[0x1a275dc]==1)
assert(not pcall(view.render,view,function() error('render failed') end))
assert(memory[0x1a275dc]==1 and memory[0x1a275d8]==7 and r.manifest.player==1)
assert(r.status=='playing' and r.active)
''')

    def test_selection_is_session_scoped_and_unavailable_in_recording_or_multiplayer(self):
        self.setup_view()
        self.check('''
for _,slot in ipairs({0,2,9,-1,1.5}) do assert(not pcall(view.select,view,slot)) end
view:select(4); r.manifest={player=1}; assert(view:player()==1)
for _,status in ipairs({'playing','finished','error'}) do r.status=status; assert(view:available()) end
r.status='loading'; assert(not view:available())
r.status='playing'; r.mode='record'; assert(not pcall(view.select,view,4))
assert(view:render(function() return memory[0x1a275dc] end)==1)
r.mode='play'; multiplayer=true; assert(not view:available() and #view:players()==0)
assert(view:render(function() return memory[0x1a275dc] end)==1)
''')
