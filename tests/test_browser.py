import unittest
import test_recorder as fixture


class BrowserTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
realNative.profile.name='SHC'
entries={}
package.loaded['code/sessions']={
 list=function() return entries end,
 load=function(id)
  for _,item in ipairs(entries) do
   if item.id==id then assert(item.status=='complete','Recording was not completed'); return item end
  end
  error('missing recording')
 end,
 compatible=function(m) return not m.different end,
}
recorder={mode='none',guard=function(_,fn) fn(); return true end,
 startPlayback=function(_,id) played=id end}
Browser=require('code/browser'); browser=Browser:new(recorder)
function entry(id,state,variant)
 return {id=id,status=state or 'complete',variant=variant or 'SHC',startTick=0,lastTick=100}
end
''')

    def test_refresh_preserves_selection_and_filters_game_variant(self):
        self.check('''
entries={entry('new'),entry('extreme','complete','Extreme'),entry('old')}
browser:refresh('old'); assert(browser.selected.id=='old' and #browser.items==2)
table.insert(entries,1,entry('newer')); browser:refresh()
assert(browser.selected.id=='old' and browser.index==3)
''')

    def test_empty_refresh_clears_old_selection(self):
        self.check('''
entries={entry('old')}; browser:refresh(); entries={}; browser:refresh()
assert(not browser.selected and not pcall(function() browser:play() end))
assert(not played)
''')

    def test_failed_capture_and_wrong_settings_cannot_play(self):
        self.check('''
entries={entry('failed','failed'),entry('different')}; entries[2].different=true
browser:refresh(); assert(not pcall(function() browser:play() end))
browser:select(2); assert(not pcall(function() browser:play() end)); assert(not played)
entries[2].different=false; browser:play(); assert(played=='different')
''')

    def test_paging_bounds_and_active_recording(self):
        self.check('''
for i=1,15 do entries[i]=entry('recording'..i) end
browser:refresh(); browser:page(1); assert(browser.index==7 and browser:firstRow()==7)
browser:page(20); assert(browser.index==15 and browser:firstRow()==13)
browser:page(-20); assert(browser.index==1 and browser:firstRow()==1)
recorder.mode='record'; assert(not pcall(function() browser:play() end)); assert(not played)
''')

    def test_malformed_summary_does_not_break_other_rows(self):
        self.check('''
entries={entry('bad'),entry('good')}; entries[1].lastTick=math.huge
browser:refresh(); assert(browser:row(1):find('0 ticks',1,true))
browser:select(2); assert(browser:row(2):find('100 ticks',1,true))
''')
