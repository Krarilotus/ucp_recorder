import unittest
import test_recorder as fixture


class PlaybackControlsTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def test_keyboard_and_visible_buttons_share_viewer_speed_without_changing_pause(self):
        self.check('''
local calls,scopes={},0
local session={mode='play',active=true,status='playing',engine={
 localSession=function() return true end,presentationSpeed=function() return 1100 end,
 withReplaySpeedInput=function(_,action) scopes=scopes+1; action() end}}
local hud=require('code/replay-hud').new(session,{available=function() return true end})
hud.controls.input=function(direction) calls[#calls+1]=direction end
local items
hud:install({attachOverlay=function(_,_,value) items=value end})
local minus,plus
for _,item in ipairs(items) do
 if item.label=='-' then minus=item elseif item.label=='+' then plus=item end
end
assert(minus and plus and minus.enabled() and plus.enabled())
assert(hud:key(0x100,187))
assert(hud:key(0x102,43) and hud:key(0x101,187) and #calls==1)
plus.action(); assert(hud:key(0x100,109)); minus.action()
assert(hud:key(0x100,107)); assert(hud:key(0x100,189))
assert(table.concat(calls,',')=='1,1,-1,-1,1,-1' and scopes==6)
for _,status in ipairs({'finished','error','recording'}) do
 session.status=status; assert(not minus.enabled() and not plus.enabled())
 assert(not hud:key(0x100,187))
end
session.status='playing'; session.mode='record'
assert(not hud:key(0x100,189))
session.mode='play'; session.engine.localSession=function() return false end
assert(not hud:key(0x100,187) and #calls==6)
''')

    def test_offline_mp_speed_input_restores_mode_even_on_failure(self):
        self.check('''
local Engine=require('code/engine')
local e=setmetatable({base=0x191d768,offline={}},{__index=Engine})
for _,mode in ipairs({0,1,2,99}) do
 memory[e.base+0x618]=mode
 for _,fail in ipairs({false,true}) do
  local ok=pcall(e.withReplaySpeedInput,e,function()
   assert(memory[e.base+0x618]==(mode==0 and 0 or 99))
   if fail then error('native input failure') end
  end)
  assert(ok~=fail and memory[e.base+0x618]==mode)
 end
end
e.offline=nil; memory[e.base+0x618]=1
assert(not pcall(e.withReplaySpeedInput,e,function() error('must not dispatch') end))
''')
