"""Restore-point state across the Map Extensions, Automarket and UCP2-Legacy setups.

Recorder must keep working with Map Extensions absent, with the released 1.0.0
(its own Automarket/Legacy adapter) and with an owner that exposes the complete
save archive. Each case checks which source fills the extension section.
"""
import struct
import unittest

import test_world_capture as world_fixture
import test_world_container as container_fixture
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


class OwnerArchiveContainerTests(unittest.TestCase):
    setUp = world_fixture.WorldCaptureTests.setUp
    capture = world_fixture.WorldCaptureTests.capture
    prepare = container_fixture.WorldContainerTests.prepare

    def test_large_owner_archive_sizes_buffers_and_survives_preparation(self):
        # 1.5 MiB: larger than every native section (70,001 bytes here) and over
        # the 1 MiB limit of the earlier Automarket/Legacy-only container.
        archive = bytes(i % 251 for i in range(1536 * 1024))
        self.lua.globals().owner_archive = archive.decode('latin-1')
        self.lua.execute("""
modules={['map-extensions']={captureSaveSection=function() return owner_archive end}}
allActiveExtensions={{name='map-extensions',version='1.2.0'}}
""")
        self.lua.execute("realMaxSection=require('code/world-codec').MAX_SECTION")
        self.prepare()
        self.lua.execute("""
local fake=package.loaded['code/world-codec']
fake.MAX_SECTION=realMaxSection -- the fixture's fake codec omits the real limit
local wrapped=fake.withBuffers
package.loaded['code/world-codec'].withBuffers=function(capacity,callback)
 bufferCapacity=capacity
 return wrapped(capacity,callback)
end
prepared=container.prepare(virtual_path,engine)
""")
        self.assertEqual(self.lua.globals().bufferCapacity, len(archive))
        data = (self.root/'world-native.sav').read_bytes()
        self.assertEqual(data[-len(archive):], archive)


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

    def test_matching_owner_interface_replaces_only_the_wrapped_byte_checks(self):
        self.check("""
Engine=require('code/engine')
realNative=require('code/native'); realNative.profile.name='SHC'
local sites=require('code/engine-sites').SHC
for _,site in pairs(sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
local interface={version=1,sectionCount=122,descriptorSize=16,packager=sites.packager,
 sections=sites.sections,readWorld=sites.readWorld.address,writeWorld=sites.save.address}
allActiveExtensions={{name='map-extensions',version='1.2.0'}}
local owner={getNativeSaveInterface=function() return interface end}
modules={['map-extensions']=owner}
-- The owner wraps these two functions; a changed sixth byte, which Recorder's
-- own 1.x hook acceptance refuses, is the owner's business when it confirms them.
bytes[sites.save.address]=0xE9; bytes[sites.readWorld.address]=0xE9
bytes[sites.save.address+5]=0
local bound=assert(Engine.verify())
assert(#bound.save.bytes==0 and #bound.readWorld.bytes==0)
assert(bound.save.address==sites.save.address and bound.readWorld.address==sites.readWorld.address)
assert(bound.packager==sites.packager and bound.sections==sites.sections and bound.load==sites.load)
-- Every other site is still checked.
bytes[sites.load.address]=(sites.load.bytes[1]+1)%256
assert(not pcall(Engine.verify))
core.writeBytes(sites.load.address,sites.load.bytes)
-- Unknown version, other functions, a broken table or a throwing owner: Recorder
-- keeps its checked static sites instead of turning itself off.
local function falls_back(label)
 printed={}
 local ok=pcall(Engine.verify)
 assert(not ok,label..': static sixth-byte check must apply again')
 local logged=false
 for _,line in ipairs(printed) do
  if tostring(line[1]):find('save interface not used',1,true) then logged=true end
 end
 assert(logged,label)
end
for key,bad in pairs({version=2,sectionCount=121,descriptorSize=20,packager=sites.packager+4,
  sections=0,readWorld=sites.readWorld.address+1,writeWorld=0x1400000}) do
 local saved=interface[key]; interface[key]=bad
 falls_back(key)
 interface[key]=saved
end
owner.getNativeSaveInterface=function() error('hooks not installed') end; falls_back('error')
owner.getNativeSaveInterface=function() return 42 end; falls_back('type')
bytes[sites.save.address+5]=sites.save.bytes[6]
local static=assert(Engine.verify())
assert(#static.save.bytes>0 and static.save.address==sites.save.address)
-- Map Extensions 1.0.0 has no interface: the static sites, as in 0.51.1.
modules={['map-extensions']={}}
allActiveExtensions={{name='map-extensions',version='1.0.0'}}
static=assert(Engine.verify())
assert(#static.save.bytes>0)
bytes[sites.save.address+5]=0
assert(not pcall(Engine.verify))
""")


class OldPointProxyTests(unittest.TestCase):
    # The game runs Lua 5.4, where the framework's table proxies iterate through
    # __pairs while next() sees an empty table. LuaJIT ignores __pairs.
    def setUp(self):
        import lupa.lua54
        import test_snapshot_store
        original = test_snapshot_store.LuaRuntime
        test_snapshot_store.LuaRuntime = lupa.lua54.LuaRuntime
        try:
            test_snapshot_store.SnapshotStoreTests.setUp(self)
        finally:
            test_snapshot_store.LuaRuntime = original

    def test_required_contracts_behind_a_proxy_still_refuse_old_points(self):
        self.lua.execute("""
point=assert(createPoint())
local contracts={module={format='module-1'}}
local proxy=setmetatable({},{__index=contracts,__pairs=function() return next,contracts,nil end})
assert(next(proxy)==nil)
modules={['map-extensions']={requiredStateContracts=function() return proxy end}}
local ok,reason=pcall(snapshot.prepare,manifest,point,path)
assert(not ok and reason:find('predates complete',1,true))
contracts.module=nil
assert(snapshot.prepare(manifest,point,path))
""")


class LoadRefusalTests(unittest.TestCase):
    check = recorder_fixture.RecorderTests.check
    setUp = recorder_fixture.RecorderTests.setUp

    def run_load(self, refusals):
        self.check("""
core.writeString=function(a,s) for i=1,#s do bytes[a+i-1]=s:byte(i) end end
local snapshots=require('code/native-snapshots')
calls={load=0,read=0,reset=0}
queue={%s}
modules={['map-extensions']={takeLoadRefusal=function()
 calls.taken=(calls.taken or 0)+1
 return table.remove(queue,1)
end}}
menu=0x5000000; gameCore=0x5100000; packager=0x5200000
for _,o in ipairs({0x58,0x7c,0x80,0x884}) do memory[menu+o]=o end
memory[gameCore+0xc]=7; memory[packager+0x20]=0x493690
state=setmetatable({sites={menuText=menu,gameCore=gameCore,packager=packager,sections=0x5300000},
 pathBuffer=0x5400000,pathOverride=0x5500000,
 singlePlayer=function() return true end,
 loadNative=function() calls.load=calls.load+1; calls.viewDuringLoad=memory[gameCore+0xc] end,
 readWorldNative=function() calls.read=calls.read+1; calls.progressDuringRead=memory[packager+0x20] end,
 resetCommands=function() calls.reset=calls.reset+1 end},{__index=snapshots})
ok,reason=pcall(state.loadSnapshot,state,'ucp/replays/x.sav')
""" % refusals)

    def test_refused_snapshot_stops_before_the_second_world_read(self):
        # The first value is a stale refusal from an earlier menu Load; it is drained.
        self.run_load("'old-provider','improved-tunnelers'")
        self.check("""
assert(not ok and reason:find('Save requires module improved-tunnelers',1,true))
assert(calls.taken==2 and calls.load==1 and calls.read==0 and calls.reset==0)
assert(memory[state.pathOverride]==0 and state.loading==false and state.overridePath==nil)
for _,o in ipairs({0x58,0x7c,0x80,0x884}) do assert(memory[menu+o]==o) end
-- Map Extensions requested the main menu; the in-game view is not restored.
assert(memory[gameCore+0xc]==20)
""")

    def test_stale_refusal_does_not_stop_an_admitted_snapshot(self):
        self.run_load("'old-provider'")
        self.check("""
assert(ok,reason)
assert(calls.load==1 and calls.read==1 and calls.reset==1 and calls.viewDuringLoad==20)
assert(calls.progressDuringRead==0 and memory[packager+0x20]==0x493690)
assert(memory[state.pathOverride]==0 and state.loading==false)
""")

    def test_released_map_extensions_without_refusal_api_loads_as_before(self):
        self.run_load("")
        self.check("""
modules={['map-extensions']={}}
calls={load=0,read=0,reset=0}
ok,reason=pcall(state.loadSnapshot,state,'ucp/replays/x.sav')
assert(ok,reason)
assert(calls.load==1 and calls.read==1 and calls.reset==1)
""")

    def test_failed_native_load_restores_the_previous_view(self):
        self.run_load("")
        self.check("""
memory[gameCore+0xc]=7
state.loadNative=function() error('native load failed') end
ok,reason=pcall(state.loadSnapshot,state,'ucp/replays/x.sav')
assert(not ok and reason:find('native load failed',1,true))
assert(memory[gameCore+0xc]==7 and memory[state.pathOverride]==0)
""")


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
