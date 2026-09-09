import unittest
import test_recorder as fixture


class PlaybackInfoTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)

    def test_summary_retains_actual_versions_and_omits_transitive_leaf_modules(self):
        self.check('''
local function extension(name,version,kind,deps)
 return {name=name,version=version,type=function() return kind end,definition={dependencies=deps or {}}}
end
local all={extension('Private-Test','0.1.22','PluginLoader',{Ascension='^1.0.0'}),
 extension('Ascension','1.0.11','PluginLoader',{AI='^1.0.0',automarket='^1.0.0'}),
 extension('AI','1.0.0','PluginLoader'),extension('automarket','1.1.0','ModuleLoader'),
 extension('recorder','0.46.0','ModuleLoader')}
local info=require('code/playback-info').capture(all,'major: 3\\nminor: 0\\npatch: 7\\n')
assert(info.framework=='3.0.7' and info.count==5)
assert(info.packs.Ascension=='1.0.11' and info.packs['Private-Test']=='0.1.22')
assert(info.packs.recorder=='0.46.0' and not info.packs.AI and not info.packs.automarket)
assert(all[2].definition.dependencies.automarket=='^1.0.0' and all[4].version=='1.1.0')
local lines=require('code/playback-info').lines({variant='Extreme'},info)
assert(lines[1]=='Extreme 1.41' and lines[#lines]=='5 exact extension versions verified')
''')

    def test_f3_repeat_toggles_once_and_never_changes_simulation_controls(self):
        self.check('''
local available=true; local recorder={}
local hud=require('code/replay-hud').new(recorder,{available=function() return available end})
assert(hud:key(0x100,114) and hud.details)
assert(hud:key(0x100,114) and hud.details)
assert(hud:key(0x101,114)); hud:key(0x100,114); assert(not hud.details)
hud:key(0x101,114); available=false; assert(not hud:key(0x100,114) and not hud.details)
assert(next(recorder)==nil)
''')
