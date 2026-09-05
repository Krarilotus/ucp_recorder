import test_session_files
import unittest


class SettingsCaptureTests(unittest.TestCase):
    setUp = test_session_files.SessionFileTests.setUp
    def test_config_changed_on_disk_does_not_change_running_game_identity(self):
        self.lua.execute('''
local originalOpen=io.open
store.write(temp_root..'/version.yml','version: 3.0.7')
io.open=function(path,mode)
 if path=='ucp/ucp-version.yml' then path=temp_root..'/version.yml' end
 return originalOpen(path,mode)
end
configFinal={recorder={fixedSeed=123},game={speed=40}}
allActiveExtensions={{name='recorder',version='0.3.0'}}
store.captureSettings()
local m=recording(); store.finish(m)
store.write(CONFIG_FILE,'settings for next launch')
assert(store.compatible(m))
store.captureSettings()
assert(not store.compatible(m))
''')

    def test_resolved_extension_version_change_requires_matching_environment(self):
        self.lua.execute('''
local originalOpen=io.open
store.write(temp_root..'/version.yml','version: 3.0.7')
io.open=function(path,mode)
 return originalOpen(path=='ucp/ucp-version.yml' and temp_root..'/version.yml' or path,mode)
end
allActiveExtensions={{name='other-module',version='1.0.0'}}
store.captureSettings(); local m=recording(); store.finish(m)
allActiveExtensions[1].version='1.0.1'
store.captureSettings(); assert(not store.compatible(m))
''')
