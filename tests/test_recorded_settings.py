"""Persist loaded options and exact extension choices independently of input text."""
import json
import unittest

import test_session_files


class RecordedSettingsTests(unittest.TestCase):
    setUp = test_session_files.SessionFileTests.setUp

    def prepare(self):
        self.lua.execute('''
yaml={eval=function(text) return json:decode(text) end}
local originalOpen=io.open
store.write(temp_root..'/version.yml','version: 3.0.7')
io.open=function(path,mode)
 return originalOpen(path=='ucp/ucp-version.yml' and temp_root..'/version.yml' or path,mode)
end
allActiveExtensions={
 {name='ui',version='1.0.1',type=function() return 'ModuleLoader' end},
 {name='recorder',version='0.25.0',type=function() return 'ModuleLoader' end},
 {name='Test-Plugin',version='1.2.3',type=function() return 'PluginLoader' end},
}
configFinal={['recorder-0.25.0']={autoRecord=true,enabled=false,speed=200,
 literal={contents={value='this is option data'},nested={1,2,3}}},['Test-Plugin-1.2.3']={}}
store.captureSettings()
''')

    def test_launch_profile_pins_order_types_and_normalized_values(self):
        self.prepare()
        profile = json.loads(self.lua.eval('store.settings().restartSettings'))
        full = profile['config-full']
        self.assertEqual(full, profile['config-sparse'])
        self.assertEqual(full['load-order'], [dict(extension='ui',version='1.0.1'),
            dict(extension='recorder',version='0.25.0'),dict(extension='Test-Plugin',version='1.2.3')])
        self.assertEqual(set(full['modules']), {'ui','recorder'})
        self.assertEqual(set(full['plugins']), {'Test-Plugin'})
        options = full['modules']['recorder']['config']['contents']['value']
        self.assertIs(options['enabled'],False)
        self.assertEqual(options['speed'],200)
        self.assertEqual(options['literal'],dict(contents=dict(value='this is option data'),nested=[1,2,3]))

    def test_relaunch_profile_is_compatible_despite_different_source_bytes(self):
        self.prepare()
        self.lua.execute('''
local settings=store.settings()
local m=recording(); store.finish(m)
local launch=json:decode(settings.restartSettings)
-- UCP's contents.value replacement yields these exact option tables.
configFinal={}
for _,category in ipairs({'modules','plugins'}) do
 for name,item in pairs(launch['config-full'][category]) do
  for _,requirement in ipairs(launch['config-full']['load-order']) do
   if requirement.extension==name then configFinal[name..'-'..requirement.version]=item.config.contents.value end
  end
 end
end
store.write(CONFIG_FILE,settings.restartSettings)
store.captureSettings()
assert(store.settings().hash~=m.settingsHash and store.compatible(m))
allActiveExtensions[1],allActiveExtensions[2]=allActiveExtensions[2],allActiveExtensions[1]
store.captureSettings(); assert(not store.compatible(m))
''')

    def test_recorded_copy_preserves_launch_profile_and_rejects_corruption(self):
        self.prepare()
        self.lua.execute('''
local m=recording(); local path=store.path(m.id)
store.write(path..'/start.sav','snapshot'); store.write(path..'/rng.bin','rng')
m.snapshotHash=sha.sha256('snapshot'); m.rngHash=sha.sha256('rng')
local copied=store.copy(m,'Saved so far',m.finalRngHash)
local target=store.path(copied.id)..'/replay-config.yml'
assert(store.read(target)==store.read(path..'/replay-config.yml'))
store.preflight(store.load(copied.id,profile))
store.write(target,'changed')
assert(not pcall(store.load,copied.id,profile))
assert(store.read(path..'/replay-config.yml')==store.settings().restartSettings)
''')

    def test_invalid_loaded_identity_cannot_silently_create_partial_profile(self):
        for failure in ('duplicate','version range','path','unknown type','unloaded config','missing extensions'):
            with self.subTest(failure=failure):
                self.prepare()
                scripts={
                    'duplicate': 'allActiveExtensions[3]=allActiveExtensions[1]',
                    'version range': "allActiveExtensions[1].version='>= 1.0.0'",
                    'path': "allActiveExtensions[1].name='../ui'",
                    'unknown type': "allActiveExtensions[1].type=function() return 'Other' end",
                    'unloaded config': 'configFinal.unloaded={}',
                    'missing extensions': 'allActiveExtensions=nil',
                }
                self.lua.execute(scripts[failure]+"; assert(not pcall(store.captureSettings))")

    def test_unknown_or_half_declared_settings_profile_cannot_load(self):
        self.prepare()
        self.lua.execute('''
local m=recording(); store.finish(m)
local original=m.restartSettingsHash
for _,failure in ipairs({'profile','missing hash','hash without profile'}) do
 m.settingsCapture='resolved-v1'; m.restartSettingsHash=original
 if failure=='profile' then m.settingsCapture='future-v2'
 elseif failure=='missing hash' then m.restartSettingsHash=nil
 else m.settingsCapture=nil end
 store.save(m); assert(not pcall(store.load,m.id,profile))
end
''')

    def test_yaml_bridge_type_coercion_is_rejected_before_capture(self):
        self.prepare()
        self.lua.execute('''
yaml.eval=function(text)
 local parsed=json:decode(text)
 parsed['config-full'].modules.recorder.config.contents.value.enabled=0
 return parsed
end
assert(not pcall(store.captureSettings))
''')

    def test_nonfinite_option_reports_its_path_before_json_can_drop_it(self):
        self.prepare()
        self.lua.execute('''
for _,number in ipairs({0/0,math.huge,-math.huge}) do
 configFinal['recorder-0.25.0'].troops={Knight=number}
 local ok,reason=pcall(store.captureSettings)
 assert(not ok and reason:find('recorder-0.25.0/troops/Knight',1,true))
end
''')
