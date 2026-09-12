"""Exercise the actual menu actions with native rendering replaced by controls."""
import unittest
import test_browser


class UIFlowTests(unittest.TestCase):
    check = test_browser.BrowserTests.check

    def test_multiplayer_named_capture_uses_local_copy_and_returns_to_status(self):
        self.check('''
recorder.engine.singlePlayer=function() return false end
local source={id='host-capture'}
local saved
recorder.engine.trace={file=true,capture=source,
 saveCopy=function(_,name) saved=name; return {displayName=name} end,
 statusLines=function() return {'Capture active','Not playable'} end}
pauseAction(); local status=shown
click('Save capture as...'); assert(inputAllowed() and shown~=status)
input(0x102,string.byte('X')); input(0x102,13)
assert(saved=='X' and shown==status and recorder.engine.trace.file and source.id=='host-capture')
click('Save capture as...'); input(0x102,27); assert(shown==status and saved=='X')
''')

    def test_portraits_select_view_without_changing_pause_or_native_actor(self):
        self.check('''local roster={}; for i=1,8 do roster[i]={kind=i==4 and 'ai' or 'empty'} end
recorder.engine.networkState=function() return {roster=roster} end
recorder.mode='play'; recorder.active=true; recorder.status='playing'; recorder.manifest={player=1}
local paused=true; recorder.engine.isPaused=function() return paused end
assert(not pauseVisible() and restartDisabled())
assert(overlayVisible()); overlayItems[2].action()
assert(menu.view:player()==4 and recorder.manifest.player==1 and paused and shown==-1)
recorder.mode='record'; assert(not overlayVisible() and not restartDisabled())
''')

    def setUp(self):
        test_browser.BrowserTests.setUp(self)
        self.check('''
local nextId=300
controls={}; dialogs={}; renders={}; texts={}; shown=-1
ui={
 installViewRender=function() end,
 attachOverlay=function(_,ids,items,visible) overlayItems=items; overlayVisible=visible end,
 modal=function(_,items,count,width,height,render,title)
  assert(count==#items)
  for i,a in ipairs(items) do
   assert(a.x>=0 and a.y>=0 and a.x+a.width<=width and a.y+a.height<=height)
   for j,b in ipairs(items) do
    if i~=j then assert(a.x+a.width<=b.x or b.x+b.width<=a.x or a.y+a.height<=b.y or b.y+b.height<=a.y) end
   end
  end
  local id=nextId; nextId=nextId+1; dialogs[id]=items
  renders[id]=function(x,y)
   if title then texts[#texts+1]=title() end
   render(x,y+(title and 32 or 0))
  end
  return id
 end,
 text=function(_,value) texts[#texts+1]=value end,
 installInput=function(_,predicate,handler) input=handler; inputAllowed=predicate end,
 extendPause=function(_,label,action,predicate,disabled) pauseLabel=label; pauseAction=action; pauseVisible=predicate; restartDisabled=disabled end,
 activeDialog=function() return shown end,
 show=function(_,id) shown=id end,
 close=function() shown=-1 end,
 button=function(_,address,x,y,w,h,label,action) controls[address]={label=label,action=action} end,
 trackVisibility=function() end,
}
package.loaded['code/native-ui']={ITEM_SIZE=80,new=function() return ui end}
package.loaded['code/fixes']={install=function(_,enabled)
 assert(enabled==recorder.playbackActive)
end}
package.loaded['code/history-native']={new=function(_,_,browser,rename)
 historyRename=rename
 return {advance=function() browser:advancePreparation() end}
end}
recorder.playbackActive=1234
recorder.engine={base=0x191d768,singlePlayer=function() return true end,isPaused=function() return false end,
 localSession=function(self) return self:singlePlayer() end,
 presentationSpeed=function() return 90 end,
 isLogicallyPaused=function(self) return self:isPaused() end}
recorder.status='idle'; recorder.autoRecord=true
require('code/platform').milliseconds=function() return 0 end
recorder.preparePlayback=function(_,id,worlds,progress)
 progress('Checking replay data...')
 return {manifest={id=id}}
end
menu=require('code/ui')
menu.createButtons(recorder,{reportPause={address=123,bytes={0,0,0,0,0,0,0}}})
function click(label)
 for _,item in ipairs(assert(dialogs[shown])) do
  local text=type(item.label)=='function' and item.label() or item.label
  if text==label then return item.action() end
 end
 error('Button missing: '..label)
end
''')

    def test_failure_details_distinguish_stopped_capture_from_failed_playback(self):
        self.check('''
recorder.status='error'; recorder.error='capture failed'; recorder.mode='record'
assert(pauseLabel()=='Replay failed - details')
pauseAction(); renders[shown](0,0)
assert(texts[3]=='Recording stopped. This match is no longer being recorded.')
assert(texts[4]=='Resume the game to continue playing normally.')
recorder.mode='play'; assert(not pauseVisible())
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
pauseAction(); click('Back'); assert(shown==5)
''')
