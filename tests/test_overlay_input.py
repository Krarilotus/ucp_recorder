import unittest
import test_recorder as fixture


class OverlayInputTests(unittest.TestCase):
    check=fixture.RecorderTests.check
    setUp=fixture.RecorderTests.setUp

    def test_native_update_owns_hover_and_captures_press_hold_and_release_before_map(self):
        self.check('''
local hook; local over=false; local visible=true; local maps,updates,completed=0,0,0
local mouse=9000; local overlay={menu=7000}
local ui={currentView=0x31000000,sites={mouse={value=mouse},menuHit={value=9500},updateMenu={address=5000,bytes={1,2,3,4,5,6}}},
 inputOverlays={[14]=6000,[16]=6000},updateOverlay=function(_,root,action)
  assert(root==6000 and action==0); return visible and overlay or nil end}
setmetatable(ui,{__index=require('code/native-ui')})
core.writeBytes(5000,ui.sites.updateMenu.bytes)
local inNative=false
core.hookCode=function(fn,address,count,convention,length)
 assert(address==5000 and count==1 and convention==1 and length==6); hook=fn
 return function(menu)
  inNative=true
  if menu==7000 then
   updates=updates+1; memory[9500]=over and 1 or 0; memory[menu+0x38]=0
  else assert(menu==7100); maps=maps+1 end
  inNative=false
 end
end
ui.onMenuUpdated=function() assert(not inNative); completed=completed+1 end
require('code/overlay-input').install(ui)
memory[0x31000000]=14
hook(7100); assert(maps==1 and updates==1)
over=true; memory[mouse+0x40]=1; hook(7100); assert(maps==1)
over=false; hook(7100); assert(maps==1 and updates==2) -- no redispatch after native seek/load
memory[mouse+0x40]=0; hook(7100); assert(maps==1 and updates==2) -- release still belongs to HUD
hook(7100); assert(maps==2) -- next ordinary input is preserved
over=true; hook(7100); assert(maps==2) -- hover also protects controls from map input
visible=false; hook(7100); assert(maps==3) -- Escape dialog keeps native behavior
memory[0x31000000]=58; hook(7100); assert(maps==4 and completed==8)
''')
