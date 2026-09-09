import unittest
import test_recorder as fixture


class PlaybackControlsTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def test_keyboard_and_visible_buttons_share_viewer_speed_without_changing_pause(self):
        self.check('''
local speed,paused,writes=300,true,0
local session={mode='play',active=true,status='playing',engine={
 localSession=function() return true end,presentationSpeed=function() return speed end,
 setPresentationSpeed=function(_,v) speed=v; writes=writes+1 end,
 isLogicallyPaused=function() return paused end}}
local hud=require('code/replay-hud').new(session,{available=function() return true end})
local items
hud:install({attachOverlay=function(_,_,value) items=value end})
local minus,plus
for _,item in ipairs(items) do
 if item.label=='-' then minus=item elseif item.label=='+' then plus=item end
end
assert(minus and plus and minus.enabled() and plus.enabled())
assert(hud:key(0x100,187) and speed==500)
assert(hud:key(0x102,43) and hud:key(0x101,187) and writes==1)
plus.action(); assert(speed==750)
assert(hud:key(0x100,109) and speed==500)
minus.action(); assert(speed==300 and paused)
assert(hud:key(0x100,107) and speed==500)
assert(hud:key(0x100,189) and speed==300)
speed=1000; assert(not plus.enabled()); hud:key(0x100,107); assert(speed==1000)
speed=20; assert(not minus.enabled()); hud:key(0x100,109); assert(speed==20)
for _,status in ipairs({'finished','error','recording'}) do
 session.status=status; assert(not minus.enabled() and not plus.enabled())
 assert(not hud:key(0x100,187) and speed==20)
end
session.status='playing'; session.mode='record'
assert(not hud:key(0x100,189) and speed==20)
session.mode='play'; session.engine.localSession=function() return false end
assert(not hud:key(0x100,187) and speed==20)
''')
