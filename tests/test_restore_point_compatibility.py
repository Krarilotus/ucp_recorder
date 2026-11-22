"""Restore-point state across the Map Extensions, Automarket and UCP2-Legacy setups.

Recorder must keep working with Map Extensions absent, with the released 1.0.0
(its own Automarket/Legacy adapter) and with an owner that exposes the complete
save archive. Each case checks which source fills the extension section.
"""
import struct
import unittest

import test_world_capture as world_fixture
import test_recorder as recorder_fixture

MARKET = struct.pack('<I', 2) + bytes(i % 256 for i in range(2412))
LEGACY = r'''
legacyCalls=0
legacy={simulationStateFormat=1,serializeSimulationState=function(_,handle)
 legacyCalls=legacyCalls+1
 handle:put('format','1'); handle:put('attack-target-cycle.bin','\1\0\0\0')
end}
'''


class ExtensionStateMatrixTests(unittest.TestCase):
    setUp = world_fixture.WorldCaptureTests.setUp
    capture = world_fixture.WorldCaptureTests.capture

    def setup_modules(self, extensions, modules):
        self.memory[0x5000000] = MARKET
        self.lua.execute(LEGACY)
        self.lua.execute('allActiveExtensions={%s}; modules={%s}' % (extensions, modules))

    def state(self):
        return self.lua.execute('''
local market,marketInfo,data,info=world.extensionState()
return market~=nil,data,info and info.complete or false
''')

    def test_without_map_extensions_and_stateful_modules_no_section_is_written(self):
        self.setup_modules('', '')
        market, data, complete = self.state()
        self.assertFalse(market)
        self.assertIsNone(data)
        self.assertFalse(complete)
        capture = self.capture()
        self.assertEqual(capture['world']['status'], 'complete')
        self.assertFalse(capture['world']['extensions'])
        self.assertIsNone(self.lua.globals().capturedExtensions)

    def test_released_map_extensions_without_stateful_modules_writes_nothing(self):
        self.setup_modules("{name='map-extensions',version='1.0.0'}", "['map-extensions']={}")
        market, data, complete = self.state()
        self.assertFalse(market)
        self.assertIsNone(data)
        self.assertFalse(complete)

    def test_released_map_extensions_keeps_the_automarket_and_legacy_adapter(self):
        self.setup_modules(
            "{name='map-extensions',version='1.0.0'},{name='protocol',version='1.0.0'},"
            "{name='automarket',version='1.1.0'},{name='ucp2-legacy',version='2.15.2'}",
            "['map-extensions']={},protocol={getProtocolNumber=function() return 130 end},"
            "automarket={pAutomarketData=0x5000000},['ucp2-legacy']=legacy")
        market, data, complete = self.state()
        self.assertTrue(market)
        self.assertEqual(data, 'zip bytes')
        # An adapter archive is not the owner's complete archive: no sectionCapture marker.
        self.assertFalse(complete)
        self.lua.execute(r'''
assert(capturedExtensions['automarket/automarketplayerdata.bin']==read_memory(0x5000000,2416))
assert(capturedExtensions['ucp2-legacy/attack-target-cycle.bin']=='\1\0\0\0')
assert(legacyCalls==1)
''')

    def test_owner_archive_replaces_both_adapters(self):
        self.setup_modules(
            "{name='map-extensions',version='1.2.0'},{name='protocol',version='1.0.0'},"
            "{name='automarket',version='1.1.0'},{name='ucp2-legacy',version='2.15.2'},"
            "{name='improved-tunnelers',version='1.7.3'}",
            "['map-extensions']={captureSaveSection=function() return 'owner archive\\0' end},"
            "protocol={getProtocolNumber=function() return 130 end},"
            "automarket={pAutomarketData=0x5000000},['ucp2-legacy']=legacy")
        self.reads.clear()
        market, data, complete = self.state()
        self.assertFalse(market)
        self.assertEqual(data, 'owner archive\0')
        self.assertTrue(complete)
        self.assertIsNone(self.lua.globals().capturedExtensions)
        self.assertEqual(self.lua.globals().legacyCalls, 0)
        self.assertNotIn((0x5000000, 2416), self.reads)

    def test_owner_archive_is_used_without_any_other_stateful_module(self):
        self.setup_modules("{name='map-extensions',version='1.2.0'}",
                           "['map-extensions']={captureSaveSection=function() return 'manifest only' end}")
        market, data, complete = self.state()
        self.assertEqual((market, data, complete), (False, 'manifest only', True))

    def test_owner_archive_limits_are_checked(self):
        for archive in ("''", "nil", "42", "string.rep('x',32*1024*1024+1)"):
            self.setup_modules("{name='map-extensions',version='1.2.0'}",
                               "['map-extensions']={captureSaveSection=function() return %s end}" % archive)
            ok = self.lua.execute('return pcall(world.extensionState)')
            self.assertFalse(ok[0] if isinstance(ok, tuple) else ok, archive)

    def test_intermediate_map_extensions_without_archive_api_skips_restore_points(self):
        # 1.0.1 and 1.1.x are not in the Store. Their required providers are not
        # visible to the adapter, so a restore point would be incomplete.
        for version in ('1.0.1', '1.1.7'):
            self.setup_modules("{name='map-extensions',version='%s'},{name='ucp2-legacy',version='2.15.2'}" % version,
                               "['map-extensions']={},['ucp2-legacy']=legacy")
            ok, reason = self.lua.execute('return pcall(world.extensionState)')
            self.assertFalse(ok, version)
            self.assertIn('captureSaveSection', reason)
            # Multiplayer evidence keeps its command journal when the world part fails.
            capture = self.capture()
            self.assertEqual(capture['status'], 'recording')
            self.assertEqual(capture['world']['status'], 'failed')


class SnapshotMarkerTests(unittest.TestCase):
    check = recorder_fixture.RecorderTests.check
    setUp = recorder_fixture.RecorderTests.setUp

    def test_only_a_complete_owner_archive_marks_the_point(self):
        self.check('''
package.loaded['code/platform']={milliseconds=function() return 0 end}
package.loaded['code/native-hash']={sha256=function(v) return string.rep('a',64) end}
package.loaded['code/world-capture']={}
local capture=package.loaded['code/world-capture']
local jobs=require('code/snapshot-jobs')
local engine={tick=function() return 7 end,rngData=function() return 'r' end,
 resourceData=function() return 's' end}
for _,complete in ipairs({true,false}) do
 capture.freeze=function() return {completeExtensionState=complete or nil,cancel=function() end,
  ready=function() return true end,close=function() end} end
 local job=assert(jobs.start(engine,'p',1,0,nil,function() end))
 assert((job.point.sectionCapture==1)==complete)
 job:cancel(); jobs.poll()
end
''')


class EngineOwnerInterfaceTests(unittest.TestCase):
    check = recorder_fixture.RecorderTests.check
    setUp = recorder_fixture.RecorderTests.setUp

    def test_owner_interface_replaces_static_save_sites_and_is_validated(self):
        self.check('''
Engine=require('code/engine')
realNative=require('code/native'); realNative.profile.name='SHC'
local sites=require('code/engine-sites').SHC
for _,site in pairs(sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
local interface={version=1,sectionCount=122,descriptorSize=16,
 packager=0x1100000,sections=0x1200000,readWorld=0x1300000,writeWorld=0x1400000}
allActiveExtensions={{name='map-extensions',version='1.2.0'}}
modules={['map-extensions']={getNativeSaveInterface=function() return interface end}}
-- The owner has resolved and verified its own patch sites; Recorder must not
-- require its static bytes there (even a changed sixth byte, which the 1.x
-- hook acceptance alone would refuse), but still checks every other site.
bytes[sites.save.address]=0xE9; bytes[sites.readWorld.address]=0xE9
bytes[sites.save.address+5]=0
local bound=assert(Engine.verify())
assert(bound.save.address==0x1400000 and bound.readWorld.address==0x1300000)
assert(bound.packager==0x1100000 and bound.sections==0x1200000)
for key,bad in pairs({version=2,sectionCount=121,descriptorSize=20,packager=0,readWorld=0x80000000}) do
 local saved=interface[key]; interface[key]=bad
 assert(not pcall(Engine.verify),key)
 interface[key]=saved
end
-- Without the interface (Map Extensions 1.0.0), the static sites stay checked:
-- its five-byte wrapper is accepted, a changed sixth byte is not.
modules={['map-extensions']={}}
allActiveExtensions={{name='map-extensions',version='1.0.0'}}
assert(not pcall(Engine.verify))
bytes[sites.save.address+5]=sites.save.bytes[6]
local static=assert(Engine.verify())
assert(static.save.address==sites.save.address and static.packager==sites.packager)
''')


class LegacyBaselineTests(unittest.TestCase):
    check = recorder_fixture.RecorderTests.check
    setUp = recorder_fixture.RecorderTests.setUp

    def test_store_legacy_is_accepted_and_unsaved_legacy_state_is_refused(self):
        self.check('''
local verify=require('code/simulation-compatibility').verify
-- No UCP2-Legacy: Recorder has no Legacy requirement.
allActiveExtensions={{name='map-extensions',version='1.0.0'}}; modules={}
verify()
-- Store 2.15.2: saved simulation state through its own registered section.
allActiveExtensions={{name='ucp2-legacy',version='2.15.2'}}
modules={['ucp2-legacy']={simulationStateFormat=1,serializeSimulationState=function() end}}
verify()
-- 2.15.1 keeps the AI attack target cycle outside saved worlds.
modules={['ucp2-legacy']={}}; allActiveExtensions={{name='ucp2-legacy',version='2.15.1'}}
local ok,reason=pcall(verify)
assert(not ok and reason:find('2.15.2',1,true))
''')


if __name__ == '__main__':
    unittest.main()
