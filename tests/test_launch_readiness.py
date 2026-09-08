"""Check the exact pinned dependency list through the same virtual reads as UCP."""
import unittest

from test_recorded_settings import RecordedSettingsTests


class LaunchReadinessTests(unittest.TestCase):
    setUp = RecordedSettingsTests.setUp
    prepare = RecordedSettingsTests.prepare

    def fixture(self):
        self.prepare()
        self.lua.execute('''
manifest=recording(); store.finish(manifest)
installed={}
for _,extension in ipairs(allActiveExtensions) do
 local category=extension:type()=='ModuleLoader' and 'modules' or 'plugins'
 installed['ucp/'..category..'/'..extension.name..'-'..extension.version..'/definition.yml']=
   json:encode({name=extension.name,version=extension.version})
end
local read=store.read
store.read=function(path)
 if path:match('^ucp/modules/') or path:match('^ucp/plugins/') then
  return assert(installed[path],'not installed')
 end
 return read(path)
end
notices={}; ERROR=-2; log=function(level,text) assert(level==ERROR); notices[#notices+1]=text end
readiness=require('code/launch-readiness')
''')

    def test_inactive_but_installed_exact_versions_are_accepted(self):
        self.fixture()
        self.lua.execute('''
allActiveExtensions={}; configFinal={}
assert(readiness.check(manifest).ready)
readiness.requireReady(manifest); assert(#notices==0)
''')

    def test_missing_versions_report_all_requirements_without_substitution(self):
        self.fixture()
        self.lua.execute('''
installed['ucp/modules/ui-1.0.1/definition.yml']=nil
installed['ucp/plugins/Test-Plugin-1.2.3/definition.yml']=nil
installed['ucp/modules/ui-1.0.2/definition.yml']=json:encode({name='ui',version='1.0.2'})
local result=readiness.check(manifest)
assert(not result.ready and #result.issues==2 and #notices==0)
assert(result.message:find('ui 1.0.1',1,true))
assert(not pcall(readiness.requireReady,manifest) and #notices==1)
assert(notices[1]:find('Test-Plugin 1.2.3',1,true))
assert(store.read(store.ROOT..'/requirements.txt')==result.details)
''')

    def test_wrong_definition_identity_and_invalid_yaml_are_unavailable(self):
        self.fixture()
        self.lua.execute('''
installed['ucp/modules/ui-1.0.1/definition.yml']=json:encode({name='ui',version='1.0.2'})
installed['ucp/plugins/Test-Plugin-1.2.3/definition.yml']='invalid YAML'
assert(#readiness.check(manifest).issues==2)
''')

    def test_changed_framework_and_damaged_settings_cannot_pass(self):
        self.fixture()
        self.lua.execute('''
store.write(temp_root..'/version.yml','version: 3.0.8')
local result=readiness.check(manifest)
assert(not result.ready and result.issues[1].kind=='framework')
store.write(store.path(manifest.id)..'/replay-config.yml','changed')
assert(not pcall(readiness.check,manifest))
''')

    def test_untrusted_identity_never_becomes_a_read_path(self):
        self.fixture()
        self.lua.execute('''
local path=store.path(manifest.id)..'/replay-config.yml'
local document=json:decode(store.read(path))
document['config-full']['load-order'][1].extension='../escape'
local raw=json:encode(document)
store.write(path,raw); manifest.restartSettingsHash=sha.sha256(raw)
assert(not pcall(readiness.check,manifest))
''')
