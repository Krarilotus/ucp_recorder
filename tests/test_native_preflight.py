"""Each hook owner verifies its sites; executable selection ignores optional hooks."""
import unittest
import test_recorder as fixture


class NativePreflightTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def prepare(self):
        self.check('''
profiles=nil
for i=1,20 do
 local name,value=debug.getupvalue(realNative.verify,i)
 if name=='profiles' then profiles=value; break end
end
assert(profiles)
function populate(profile)
 bytes={}
 core.writeBytes(0x400000,{0x4d,0x5a})
 core.writeBytes(0x40003c,{0x18,1,0,0})
 core.writeBytes(0x400118,profile.header)
end
''')

    def test_header_selects_variant_without_fixed_lifecycle_bindings(self):
        self.prepare()
        self.check('''
for _,profile in ipairs(profiles) do
 populate(profile)
 assert(realNative.verify()==profile)
 assert(profile.sites==nil and profile.addresses==nil and realNative.addr==nil)
end
''')

    def test_invalid_headers_clear_previous_variant(self):
        self.prepare()
        self.check('''
for _,address in ipairs({0x400000,0x40003c,0x400118,0x400120,0x400140}) do
 populate(profiles[1]); assert(realNative.verify()==profiles[1])
 bytes[address]=0xcc
 assert(not pcall(realNative.verify) and realNative.profile==nil)
end
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
 assert(realNative.verify()==profile)
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
