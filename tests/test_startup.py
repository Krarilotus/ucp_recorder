"""Startup failures must be diagnosable before recorder patches are installed."""
import unittest
import test_recorder as fixture


class StartupTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
realNative.profile.name='SHC'
startup=require('code/startup')
allActiveExtensions={{name='map-extensions',version='1.0.0'},
 {name='recorder',version='0.26.0'}}
report=nil; reportClosed=false
ERROR=-2; notifications={}
log=function(level,message)
 assert(level==ERROR)
 notifications[#notifications+1]=message
end
io.open=function(path,mode)
 assert(path==startup.REPORT and mode=='wb')
 return {write=function(_,data) report=data; return true end,
 close=function() reportClosed=true; return true end}
end
''')

    def test_success_report_contains_order_and_stages_without_option_values(self):
        self.check('''
configFinal={private='must not be logged'}
local result=startup.run(function(stage,install)
 assert(stage('test stage',function() return 42 end)==42)
 install(function() end)
end)
assert(result.status=='ready' and #notifications==0)
assert(reportClosed and report:find('1. map-extensions 1.0.0',1,true))
assert(report:find('2. recorder 0.26.0',1,true) and report:find('OK: test stage',1,true))
assert(report:find('READY:',1,true) and report:find('gameplay not validated',1,true))
assert(not report:find(configFinal.private,1,true))
''')

    def test_report_preserves_failure_stage_and_original_byte_details(self):
        self.check('''
local result=startup.run(function(stage)
 stage('session hook checks',function()
  require('code/hook-check').verify({address=0x474480,bytes={0x83,0xec,0x10,0x53,0x55,0x56}},
   'Recorder session hook conflicts at save',{0xe8,1,2,3,4,0},5)
 end)
 error('must not continue')
end)
assert(result.status=='disabled' and reportClosed and report:find('DISABLED: session hook checks',1,true))
assert(report:find('0x00474480',1,true))
assert(report:find('expected [** ** ** ** ** 56], found [E8 01 02 03 04 00]',1,true))
assert(not report:find('READY:',1,true) and notifications[1]:find(startup.REPORT,1,true))
assert(notifications[1]:find('No replay will be recorded',1,true))
''')

    def test_report_io_failure_cannot_mask_startup_error_or_break_success(self):
        self.check('''
for _,kind in ipairs({'open','write','close'}) do
 io.open=function()
  if kind=='open' then return nil,'open denied' end
  return {write=function() if kind=='write' then return nil,'write denied' end; return true end,
   close=function() if kind=='close' then return nil,'close denied' end; return true end}
 end
 assert(startup.run(function(_,install) install(function() end) end).status=='ready')
 local result=startup.run(function() error('original conflict') end)
 assert(result.status=='disabled' and result.reason:find('original conflict',1,true))
 assert(not result.reason:find('denied',1,true))
end
''')

    def test_installation_failure_is_fatal_and_cannot_be_misreported_as_disabled(self):
        self.check('''
local ok,reason=pcall(startup.run,function(_,install)
 install(function() error('partial native patch') end)
end)
assert(not ok and tostring(reason):find('partial native patch',1,true))
assert(report:find('FAILED: hook and menu installation',1,true))
assert(not report:find('DISABLED:',1,true) and #notifications==0)
''')

    def test_missing_installation_or_notification_cannot_report_ready(self):
        self.check('''
assert(startup.run(function() end).status=='disabled')
assert(not report:find('READY:',1,true))
log=function() error('notification unavailable') end
local ok,reason=pcall(startup.run,function() error('check failed') end)
assert(not ok and tostring(reason):find('notification unavailable',1,true))
assert(report:find('check failed',1,true))
''')

    def test_short_native_reads_are_reported_as_missing_bytes(self):
        self.check('''
local ok,reason=pcall(require('code/hook-check').verify,
 {address=0x123456,bytes={1,2,3}},'short read',{1})
assert(not ok and tostring(reason):find('found [01 ?? ??]',1,true))
''')

    def prepare_enable(self):
        self.check('''
nativeSites=require('code/engine-sites').SHC
for _,site in pairs(nativeSites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
for _,site in pairs(require('code/network-sites').SHC) do core.writeBytes(site.address,site.bytes) end
for _,site in ipairs({{address=0x46a800,bytes={139,129,76,156,0,0}},
 {address=0x46a7d0,bytes={139,129,72,156,0,0}},require('code/world-hash-sites').SHC}) do
 core.writeBytes(site.address,site.bytes)
end
realNative.verify=function() return realNative.profile end
require('code/native-ui').verify=function() return {} end
require('code/history-native').verify=function() return {} end
require('code/battle-statistics').verify=function() return {} end
require('code/fixes').verify=function() return {} end
require('code/sessions').captureSettings=function() error('settings sentinel') end
modules={['map-extensions']={}}
function noMutation() error('unexpected recorder mutation') end
core.allocate=noMutation; core.allocateCode=noMutation; core.writeCode=noMutation
core.detourCode=noMutation; core.hookCode=noMutation; core.exposeCode=noMutation
function launch(diagnostics)
 local result=require('init'):enable({multiplayerDiagnostics=diagnostics,autoRecord=false})
 assert(require('init').startup==result)
 return result
end
''')

    def test_every_diagnostic_family_is_checked_before_recorder_installation(self):
        for family in ('network', 'rng', 'world'):
            with self.subTest(family=family):
                self.setUp()
                self.prepare_enable()
                self.lua.globals().family = family
                self.check('''
local site=family=='network' and select(2,next(require('code/network-sites').SHC))
 or family=='rng' and {address=0x46a800} or require('code/world-hash-sites').SHC
bytes[site.address]=0xcc
local result=launch(true)
assert(result.status=='disabled' and report:find('diagnostic checks',1,true))
assert(report:find('conflicts',1,true) and not result.reason:find('unexpected recorder mutation',1,true))
assert(not report:find('settings sentinel',1,true))
-- Disabled diagnostics do not impose these optional byte requirements.
result=launch(false)
assert(result.status=='disabled' and result.reason:find('settings sentinel',1,true))
''')

    def test_automarket_version_failure_precedes_native_allocation(self):
        self.prepare_enable()
        self.check('''
allActiveExtensions[#allActiveExtensions+1]={name='automarket',version='1.0.0'}
local result=launch(false)
assert(result.status=='disabled' and report:find('DISABLED: Automarket compatibility',1,true))
assert(result.reason:find('requires Automarket 1.1.0',1,true))
assert(not result.reason:find('unexpected recorder mutation',1,true))
''')

    def test_singleplayer_attribution_checks_rng_hooks_before_installation(self):
        self.prepare_enable()
        self.check('''
bytes[0x46a7d0]=0xcc
local result=require('init'):enable({singleplayerRngDiagnostics=true})
assert(result.status=='disabled' and report:find('DISABLED: RNG diagnostic checks',1,true))
assert(not result.reason:find('unexpected recorder mutation',1,true))
assert(not result.reason:find('settings sentinel',1,true))
''')

    def test_supported_save_wrappers_on_both_variants_keep_strict_tail_checks(self):
        self.check('''
local Engine=require('code/engine')
modules={['map-extensions']={}}
for variant,sites in pairs(require('code/engine-sites')) do
 realNative.profile.name=variant
 for _,site in pairs(sites) do
  if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
 end
 for _,opcode in ipairs({0xe8,0xe9}) do
  core.writeBytes(sites.save.address,{opcode,1,2,3,4,0x56})
  assert(Engine.verify()==sites)
  allActiveExtensions[1].version='9.0.0'
  assert(not pcall(Engine.verify))
  allActiveExtensions[1].version='1.0.0'
  bytes[sites.save.address+5]=0xcc
  local ok,reason=pcall(Engine.verify)
  assert(not ok and tostring(reason):find('conflicts at save',1,true))
 end
end
''')
