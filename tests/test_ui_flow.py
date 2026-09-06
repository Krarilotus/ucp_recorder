"""Exercise the actual menu actions with native rendering replaced by controls."""
import unittest
import test_browser


class UIFlowTests(unittest.TestCase):
    check = test_browser.BrowserTests.check

    def setUp(self):
        test_browser.BrowserTests.setUp(self)
        self.check('''
local nextId=300
controls={}; dialogs={}; shown=-1
ui={
 modal=function(_,items,count,width,height,render)
  assert(count==#items)
  for i,a in ipairs(items) do
   assert(a.x>=0 and a.y>=0 and a.x+a.width<=width and a.y+a.height<=height)
   for j,b in ipairs(items) do
    if i~=j then assert(a.x+a.width<=b.x or b.x+b.width<=a.x or a.y+a.height<=b.y or b.y+b.height<=a.y) end
   end
  end
  local id=nextId; nextId=nextId+1; dialogs[id]=items; return id
 end,
 installInput=function(_,predicate,handler) input=handler end,
 extendPause=function(_,label,action,predicate) pauseAction=action; pauseVisible=predicate end,
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
  if item.label==label then return item.action() end
 end
 error('Button missing: '..label)
end
function browse()
 for _,item in pairs(controls) do if item.label=='Replays' then return item.action() end end
 error('Replay entry missing')
end
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
