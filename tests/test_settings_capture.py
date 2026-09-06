import test_session_files
import unittest


class SettingsCaptureTests(unittest.TestCase):
    def setUp(self):
        test_session_files.SessionFileTests.setUp(self)
        self.lua.execute('yaml={eval=function(text) return json:decode(text) end}')
    def test_config_changed_on_disk_does_not_change_running_game_identity(self):
        self.lua.execute('''
local originalOpen=io.open
store.write(temp_root..'/version.yml','version: 3.0.7')
io.open=function(path,mode)
 if path=='ucp/ucp-version.yml' then path=temp_root..'/version.yml' end
 return originalOpen(path,mode)
end
configFinal={['recorder-0.3.0']={fixedSeed=123}}
allActiveExtensions={{name='recorder',version='0.3.0',type=function() return 'ModuleLoader' end}}
store.captureSettings()
local m=recording(); store.finish(m)
store.write(CONFIG_FILE,'settings for next launch')
assert(store.compatible(m))
store.captureSettings()
assert(store.compatible(m)) -- raw formatting/content is not the loaded effective configuration
configFinal['recorder-0.3.0'].fixedSeed=124
store.captureSettings(); assert(not store.compatible(m))
''')

    def test_resolved_extension_version_change_requires_matching_environment(self):
        self.lua.execute('''
local originalOpen=io.open
store.write(temp_root..'/version.yml','version: 3.0.7')
io.open=function(path,mode)
 return originalOpen(path=='ucp/ucp-version.yml' and temp_root..'/version.yml' or path,mode)
end
configFinal={}
allActiveExtensions={{name='other-module',version='1.0.0',type=function() return 'ModuleLoader' end}}
store.captureSettings(); local m=recording(); store.finish(m)
allActiveExtensions[1].version='1.0.1'
store.captureSettings(); assert(not store.compatible(m))
''')
