import unittest
import test_recorder as fixture


class BrowserTests(unittest.TestCase):
    def test_newly_completed_full_recording_is_selected_once(self):
        self.check('''
entries={entry('old')}; browser:refresh()
table.insert(entries,1,entry('full')); recorder.lastCompletedReplay='full'
browser:refresh(); assert(browser.selected.id=='full')
browser:select(2); browser:refresh(); assert(browser.selected.id=='old')
table.insert(entries,1,entry('next')); recorder.lastCompletedReplay='next'
browser:refresh(); assert(browser.selected.id=='next')
''')
    def test_double_click_requires_same_recording_and_survives_clock_wrap(self):
        self.check('''
entries={entry('one'),entry('two')}; browser:refresh()
assert(not browser:click(1,4294967200))
assert(browser:click(1,100))
assert(not browser:click(2,150))
assert(not browser:click(2,650)) -- native threshold is strictly below 500 ms
browser:select(1); assert(not browser:click(2,700)) -- keyboard movement breaks the pair
assert(not browser:click(99,701) and browser.index==2)
''')
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
 title=function(m) return m.displayName or m.id end,
 settings=function() return {hash=currentSettings or 'current'} end,
 rename=function(id,name) for _,item in ipairs(entries) do if item.id==id then item.displayName=name end end end,
}
package.loaded['code/restart']={queue=function(id) restarted=id end}
recorder={mode='none',guard=function(_,fn) fn(); return true end,
 startPlayback=function(_,id) played=id end}
Browser=require('code/browser'); browser=Browser:new(recorder)
function entry(id,state,variant)
 return {id=id,status=state or 'complete',variant=variant or 'SHC',startTick=0,lastTick=100,settingsHash='recorded'}
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
browser:select(2); assert(not browser:play()); assert(not played and restarted=='different')
entries[2].different=false; browser:play(); assert(played=='different')
''')

    def test_matching_config_but_different_modules_does_not_restart_forever(self):
        self.check('''
entries={entry('different')}; entries[1].different=true; currentSettings='recorded'
browser:refresh(); assert(not pcall(function() browser:play() end))
assert(not restarted and not played)
''')

    def test_pinned_profile_allows_one_restart_then_blocks_unresolved_environment(self):
        self.check('''
entries={entry('locked')}; entries[1].different=true
entries[1].settingsCapture='resolved-v1'; entries[1].restartSettingsHash='pinned'
currentSettings='recorded'; browser:refresh(); assert(not browser:play() and restarted=='locked')
restarted=nil; currentSettings='pinned'; browser:refresh()
assert(not pcall(function() browser:play() end) and not restarted)
assert(browser.message:find('Install'))
''')

    def test_rename_keeps_identity_selection_and_displays_name(self):
        self.check('''
entries={entry('one'),entry('two')}; browser:refresh('two')
browser:rename('Stream match'); assert(browser.selected.id=='two' and browser.index==2)
assert(browser:row(2):find('Stream match',1,true))
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
