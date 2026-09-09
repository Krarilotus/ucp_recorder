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
package.loaded['code/launch-readiness']={check=function() return {ready=true} end,requireReady=function() end}
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

    def test_missing_version_is_shown_even_when_config_text_matches(self):
        self.check('''
package.loaded['code/launch-readiness']={
 check=function() return {ready=false,message='Required: ui 1.0.1'} end,
 requireReady=function() error('Required: ui 1.0.1') end,
}
entries={entry('missing')}; entries[1].different=true; currentSettings='recorded'
browser:refresh(); assert(browser.message=='Required: ui 1.0.1')
local ok,reason=pcall(function() browser:play() end)
assert(not ok and reason:find('ui 1.0.1',1,true) and not restarted and not played)
''')

    def test_active_recording_cannot_start_playback(self):
        self.check('''
entries={entry('one')}; browser:refresh()
recorder.mode='record'; assert(not pcall(function() browser:play() end)); assert(not played)
''')
