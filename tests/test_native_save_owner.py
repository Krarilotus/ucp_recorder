"""Recorder consumes the actual Map owner; native file I/O remains a stand-in."""
import os
from pathlib import Path
import unittest

import test_recorder as fixture


class NativeSaveOwnerTests(unittest.TestCase):
    setUp=fixture.RecorderTests.setUp
    check=fixture.RecorderTests.check

    def test_relocated_map_entries_retain_both_wrappers_and_custom_sections(self):
        path=Path(os.environ.get('UCP_MAP_TEST_ROOT',
            Path(__file__).resolve().parents[2]/'aic-tactics-map-native-interface'))
        self.lua.globals().map_root=path.as_posix()
        self.check('''
package.path=map_root..'/?.lua;'..package.path
local sites,wrappers,scanCount,callCount={},{},0,0
local serial=0x30000000
core.AOBScan=function(pattern)
 scanCount=scanCount+1; assert(not sites[pattern]);serial=serial+0x1000
 sites[pattern]=serial;return serial
end
core.readInteger=function() return 0x40000000 end
core.hookCode=function(callback,address,count,convention,size)
 assert(count==2 and convention==1 and size==5);wrappers[address]=callback
 return function(this,sections)
  assert(this==0x40000000 and sections==0x50000000)
  callCount=callCount+1;return 4321
 end
end
core.detourCode=function(_,_,size) assert(size==7) end
CallingConvention={THISCALL=1}
local game=require('mapextensions.game')
local before,after=0,0
game.registerReadWriteSavHooks(0x50000000,1337,{
 beforeReadSav=function() before=before+1 end,afterReadSav=function() after=after+1 end,
 beforeWriteSav=function() before=before+1 end,afterWriteSav=function() after=after+1 end})
package.loaded['mapextensions.memory']={}
package.loaded['mapextensions.callbacks']={}
package.loaded['mapextensions.registry']={registry={}}
modules['map-extensions']=dofile(map_root..'/init.lua')
local native=game.getNativeSaveInterface()
local scans=scanCount
local base=require('code/engine-sites').SHC
local resolved=require('code/native-save').bind(base)
assert(base.save==nil and base.readWorld==nil and base.packager==nil and base.sections==nil)
assert(resolved.save.address==native.writeWorld and resolved.readWorld.address==native.readWorld)
assert(resolved.packager==native.packager and resolved.sections==native.sections)
core.exposeCode=function(address,count,convention)
 if wrappers[address] then assert(count==2 and convention==1); return wrappers[address] end
 return function() end
end
local engine=require('code/engine').new(resolved)
assert(engine.saveNative(engine.sites.packager,engine.sites.sections)==4321)
assert(engine.readWorldNative(engine.sites.packager,engine.sites.sections)==4321)
assert(before==2 and after==2 and callCount==2 and scanCount==scans)
''')

    def test_missing_incompatible_or_invalid_owner_never_returns_a_fixed_fallback(self):
        self.check('''
local binding=require('code/native-save')
for _,key in ipairs({'version','sectionCount','descriptorSize','packager','sections','readWorld','writeWorld'}) do
 local value=mapSaveFixture();value[key]=0
 modules['map-extensions']={getNativeSaveInterface=function() return value end}
 assert(not pcall(binding.bind,{}),key)
end
modules['map-extensions']={};assert(not pcall(binding.bind,{}))
modules={};assert(not pcall(binding.bind,{}))
''')
