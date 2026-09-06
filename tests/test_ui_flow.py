"""Exercise the actual menu actions with native rendering replaced by controls."""
import unittest
import test_browser


class UIFlowTests(unittest.TestCase):
    check = test_browser.BrowserTests.check

    def test_keyboard_navigation_rename_and_remove_cancel_preserve_selection(self):
        self.check('''
entries={}; for i=1,9 do entries[i]=entry('replay'..i) end
browse(); local library=shown
input(0x100,40); assert(menu.browser.index==2)
input(0x100,34); assert(menu.browser.index==8 and menu.browser:firstRow()==7)
input(0x100,36); assert(menu.browser.index==1)
input(0x100,113); assert(shown~=library)
input(0x102,27); assert(shown==library)
input(0x100,46); assert(shown~=library)
click('Cancel'); assert(shown==library and menu.browser.index==1 and #menu.browser.items==9)
input(0x102,13); assert(played=='replay1' and shown==-1)
''')

    def test_view_selector_only_changes_presentation_choice(self):
        self.check('''
local roster={}; for i=1,8 do roster[i]={kind=i==4 and 'ai' or 'empty'} end
recorder.engine.networkState=function() return {roster=roster} end
recorder.mode='play'; recorder.active=true; recorder.status='playing'; recorder.manifest={player=1}
pauseAction(); click('View player'); click('Player 4')
assert(shown==5 and menu.view:player()==4 and recorder.manifest.player==1)
recorder.mode='record'; assert(not menu.view:available())
''')

    def setUp(self):
        test_browser.BrowserTests.setUp(self)
        self.check('''
local nextId=300
controls={}; dialogs={}; renders={}; texts={}; shown=-1
ui={
 installViewRender=function() end,
 modal=function(_,items,count,width,height,render)
  assert(count==#items)
  for i,a in ipairs(items) do
   assert(a.x>=0 and a.y>=0 and a.x+a.width<=width and a.y+a.height<=height)
   for j,b in ipairs(items) do
    if i~=j then assert(a.x+a.width<=b.x or b.x+b.width<=a.x or a.y+a.height<=b.y or b.y+b.height<=a.y) end
   end
  end
  local id=nextId; nextId=nextId+1; dialogs[id]=items; renders[id]=render; return id
 end,
 text=function(_,value) texts[#texts+1]=value end,
 installInput=function(_,predicate,handler) input=handler; inputAllowed=predicate end,
 extendPause=function(_,label,action,predicate) pauseLabel=label; pauseAction=action; pauseVisible=predicate end,
 activeDialog=function() return shown end,
 show=function(_,id) shown=id end,
 close=function() shown=-1 end,
 button=function(_,address,x,y,w,h,label,action) controls[address]={label=label,action=action} end,
 trackVisibility=function() end,
}
package.loaded['code/native-ui']={ITEM_SIZE=80,new=function() return ui end}
recorder.engine={singlePlayer=function() return true end}
recorder.status='idle'; recorder.autoRecord=true
menu=require('code/ui'); menu.createButtons(recorder,{})
function click(label)
 for _,item in ipairs(assert(dialogs[shown])) do
  local text=type(item.label)=='function' and item.label() or item.label
  if text==label then return item.action() end
 end
 error('Button missing: '..label)
end
function browse()
 for _,item in pairs(controls) do
  local text=type(item.label)=='function' and item.label() or item.label
  if text=='Replays' then return item.action() end
 end
 error('Replay entry missing')
end
''')

    def test_failure_details_distinguish_stopped_capture_from_failed_playback(self):
        self.check('''
recorder.status='error'; recorder.error='capture failed'; recorder.mode='record'
assert(pauseLabel()=='Replay failed - details')
pauseAction(); renders[shown](0,0)
assert(texts[3]=='Recording stopped. This match is no longer being recorded.')
assert(texts[4]=='Resume the game to continue playing normally.')
recorder.mode='play'; texts={}; pauseAction(); renders[shown](0,0)
assert(texts[3]=='Playback failed. Leave the mission to return to the library.')
''')

    def test_pause_save_copy_cancel_and_confirmation_keep_capture_active(self):
        self.check('''
local copies=0
recorder.mode='record'; recorder.status='recording'; recorder.active=true; recorder.observedTick=true
recorder.manifest={id='ongoing'}
recorder.saveCopy=function(_,name) copies=copies+1; assert(name=='Stream'); return {id='copy',displayName=name} end
assert(pauseVisible()); pauseAction(); local editor=shown
input(0x102,27); assert(shown==5 and copies==0 and recorder.active)
pauseAction(); for c in ('Stream'):gmatch('.') do input(0x102,c:byte()) end
input(0x102,13)
assert(copies==1 and shown~=editor and menu.browser.message=='Saved: Stream')
click('Back'); assert(shown==5 and recorder.active and recorder.status=='recording')
''')

    def test_library_rename_and_play_choose_the_recorded_settings(self):
        self.check('''
entries={entry('one'),entry('two')}; entries[1].different=true
browse(); local library=shown; click('Rename replay...')
for c in ('Named match'):gmatch('.') do input(0x102,c:byte()) end
click('Save name'); assert(shown==library and menu.browser.selected.displayName=='Named match')
click('Play'); assert(restarted=='one' and not played and shown==library)
entries[1].different=false; menu.browser:refresh(); click('Play')
assert(played=='one' and shown==-1)
''')

    def test_multiplayer_pause_explains_capture_without_opening_save_or_library(self):
        self.check('''
recorder.engine.singlePlayer=function() return false end
recorder.status='recording'; recorder.observedTick=true
recorder.saveCopy=function() error('MP must not use SP snapshot saving') end
assert(pauseVisible() and not inputAllowed())
pauseAction(); assert(shown==menu.statusDialog and inputAllowed())
renders[shown](0,0)
assert(texts[2]=='Multiplayer replay recording is not available.')
recorder.engine.trace={statusLines=function() return {'Test capture saved.','Further actions are not being saved.'} end}
texts={}; renders[shown](0,0)
assert(texts[2]=='Test capture saved.' and texts[3]=='Further actions are not being saved.')
input(0x102,27); assert(shown==5 and not inputAllowed())
browse(); assert(shown==5)
pauseAction(); click('Back'); assert(shown==5)
''')
