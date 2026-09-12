"""Each hook owner verifies its sites; executable selection ignores optional hooks."""
import unittest
import test_recorder as fixture


class NativePreflightTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def prepare(self):
        self.check('''
profiles={{name='SHC'},{name='Extreme'}}
function populate(profile) extreme=profile.name=='Extreme';bytes={} end
major='1';minor='41';identityCalls=0;hashCalls=0
data={version={getGameVersionMajor=function() return major end,
 getGameVersionMinor=function() return minor end,isExtreme=function() return extreme end}}
package.loaded['code/platform']={identity=function()
 identityCalls=identityCalls+1;return {executable='C:/Games/Crusader/test.exe'} end}
require('code/native-hash').file=function(path,limit)
 assert(path=='C:/Games/Crusader/test.exe' and limit==64*1024*1024)
 hashCalls=hashCalls+1;return string.rep(extreme and 'b' or 'a',64) end
''')

    def test_framework_selects_variant_without_fixed_lifecycle_bindings(self):
        self.prepare()
        self.check('''
for _,profile in ipairs(profiles) do
 populate(profile)
 local result=realNative.verify();assert(result.name==profile.name)
 assert(result.sha256==string.rep(extreme and 'b' or 'a',64))
 assert(result.sites==nil and result.addresses==nil and result.header==nil and realNative.addr==nil)
end
assert(identityCalls==2 and hashCalls==2)
''')

    def test_unsupported_version_or_unreadable_executable_clears_previous_identity(self):
        self.prepare()
        self.check('''
for _,bad in ipairs({'40','42','invalid'}) do
 minor='41';populate(profiles[1]);assert(realNative.verify().name=='SHC')
 minor=bad
 assert(not pcall(realNative.verify) and realNative.profile==nil)
end
assert(hashCalls==3)
minor='41';major='2';assert(not pcall(realNative.verify) and realNative.profile==nil)
major='1';require('code/native-hash').file=function() error('cannot read') end
assert(not pcall(realNative.verify) and realNative.profile==nil)
require('code/native-hash').file=function() return 'malformed' end
assert(not pcall(realNative.verify) and realNative.profile==nil)
data=nil;assert(not pcall(realNative.verify) and realNative.profile==nil)
''')

    def test_unused_seed_site_is_neither_required_nor_patched(self):
        self.prepare()
        self.check('''
local fixes=require('code/fixes')
for _,profile in ipairs(profiles) do
 populate(profile); realNative.verify()
 local sites=require('tests/fixtures/scoped-sites')[profile.name]
 local seed
 for _,site in ipairs(sites) do
  core.writeBytes(site.address,site.bytes)
  if site.kind=='seed' then seed=site end
 end
 bytes[seed.address]=0xcc
 assert(realNative.verify().name==profile.name)
 assert(fixes.verify()==sites)
 local ok,reason=pcall(fixes.verify,123)
 assert(not ok and tostring(reason):find('conflicts at seed',1,true))
 local originalWrite=core.writeCode
 core.writeCode=function(address,code)
  assert(address~=seed.address,'disabled seed hook was patched')
 end
 fixes.install(sites,0x100000,0x100004,nil)
 core.writeCode=originalWrite
 bytes[sites[1].address]=0xcc
 assert(not pcall(fixes.verify)) -- required simulation hook remains strict
end
''')
