"""Portable LuaJIT regressions; no game process or native patching required.

Run: python -m pip install lupa && python -m unittest discover -s tests -v
"""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().source_root = ROOT.as_posix()
        self.lua.execute(r'''
package.path = source_root .. '/?.lua;' .. package.path
printed={}; print=function(...) printed[#printed+1]={...} end
ERROR=-2; log=function(...) print(...) end
memory, bytes, callbacks, files, handles, scheduled = {}, {}, {}, {}, {}, 0
local nextAddress = 0x10000000
core = {
  allocate = function(size) local a=nextAddress; nextAddress=a+size+16; return a end,
  readInteger = function(a) return memory[a] or 0 end,
  writeInteger = function(a,v) memory[a]=v end,
  readSmallInteger = function(a) return memory[a] or 0 end,
  writeSmallInteger = function(a,v) memory[a]=v end,
  readBytes = function(a,n) local t={}; for i=1,n do t[i]=bytes[a+i-1] or 0 end; return t end,
  readString = function(a,n)
    local t={}; for i=1,n do t[i]=string.char(bytes[a+i-1] or 0) end
    return table.concat(t)
  end,
  writeBytes = function(a,t) for i,v in ipairs(t) do bytes[a+i-1]=v end end,
  writeCode = function() end, copyMemory = function() end,
  AssemblyLambda = function(s,vars) return {assembly=s, variables=vars} end,
  detourCode = function(f,a) callbacks[a]=f end, insertCode = function() end,
  allocateCode = function() nextAddress=nextAddress+128; return nextAddress end,
  exposeCode = function() return function() scheduled=scheduled+1 end end,
}
utils = {createLuaFunctionWrapper=function() return 0 end}
hooks = {registerHookCallback=function() end}
json = {encode=function(_,value) return value end, decode=function(_,value) return value end}
io.open = function(path,mode)
  mode=mode:gsub('b','')
  if path==failPath then return nil, 'injected failure' end
  if mode=='r' and not files[path] then return nil, 'missing' end
  if mode=='w' then files[path]={} end
  local cursor=0
  local handle={closed=false}
  function handle:read() cursor=cursor+1; return files[path][cursor] end
  function handle:write(line) table.insert(files[path],line); return self end
  function handle:flush() return true end
  function handle:close() assert(not self.closed); self.closed=true; return true end
  function handle:seek(_,offset) cursor=offset; return offset end
  handles[#handles+1]=handle
  return handle
end
os.remove=function(path) files[path]=nil; return true end
realNative = require('code/native')
realNative.profile={addresses=setmetatable({}, {__index=function(_,a) return a end})}
function mapSaveFixture()
 local extreme=realNative.profile.name=='Extreme'
 return {version=1,sectionCount=122,descriptorSize=16,
  sections=extreme and 0xb92be8 or 0xb92a58,packager=extreme and 0xf2b850 or 0xf2b3d0,
  readWorld=extreme and 0x474c50 or 0x474a20,writeWorld=extreme and 0x4746b0 or 0x474480}
end
mapSaveOwner={getNativeSaveInterface=mapSaveFixture}
function commandFixture()
 local extreme=realNative.profile.name=='Extreme'
 local base=extreme and 0x23547d8 or 0x191d768
 return {version=1,handler=base,ring=base+0x3c67c,stride=1272,capacity=200,
  writeIndex=base+(extreme and 0x166370 or 0x109ee0),currentCommand=base+0x2d824,
  localPlayer=extreme and 0x24baadc or 0x1a275dc,tick=extreme and 0x2a7b2a8 or 0x1fe7da8,
  receivedParameters=base+0xcdc,scheduleCommand=function() scheduled=scheduled+1 end}
end
commandOwner={getNativeCommandInterface=commandFixture}
modules={['map-extensions']=mapSaveOwner,protocol=commandOwner}
package.loaded['code/engine-sites']=require('tests/fixtures/engine-sites')
package.loaded['code/engine-state-sites']={bind=function(sites) return sites end,verify=function() end}
package.loaded['code/engine-command-sites']={bind=function(sites) return sites end,verify=function() end}
for _,name in ipairs({'network-sites','world-hash-sites','maintenance-sites'}) do
 local fixture=require('tests/fixtures/'..name)
 fixture.resolve=function() return fixture[realNative.profile.name or 'SHC'] end
 package.loaded['code/'..name]=fixture
end
package.loaded['code/rng-bindings']={resolve=function()
 return {state=realNative.profile.name=='Extreme' and 0x24baec0 or 0x1a279c0,streams={
  {address=0x46a800,bytes={139,129,76,156,0,0}},
  {address=0x46a7d0,bytes={139,129,72,156,0,0}}}}
end}
-- Session/dispatch fixtures replace the OS hashing boundary; native-hash has its own real API tests.
require('code/native-hash').sha256=function(data) return sha.sha256(data) end
Recorder = require('code/replay-streams')
function fixture(name)
  local r=Recorder:new({name=name,rngLogMethod='trace'})
  files[r.commandsFileName]={}
  files[r.rngFileName]={}
  files[r.infoFileName]={{gameType=0,mapSeed=1,matchSeed=1,RNGvalue1=1,RNGvalue2=1,RNGindex1=1,RNGindex2=1}}
  return r
end
function resourceState(value) local t={}; for i=1,200 do t[i]=value or 0 end; return t end
function command(tick) return {time=tick or 1,commandCategory=34,player=1,size=1,data='01'} end
function allClosed() for _,h in ipairs(handles) do assert(h.closed) end end
''')

    def check(self, script):
        self.lua.execute(script)

    def test_reset_drops_prefetch_and_is_idempotent(self):
        self.check('''
local r=fixture('cache'); files[r.commandsFileName]={command(685)}
r:openFiles('r'); assert(r:peekCommand().time==685)
r:reset(); r:reset(); files[r.commandsFileName]={command(114)}
r:openFiles('r'); assert(r:consumeSavedCommand().time==114)
r:reset(); allClosed()
''')

    def test_missing_and_partial_files_do_not_commit_state(self):
        self.check('''
local r=Recorder:new({name='missing'}); memory[0x191de0c]=777
assert(not pcall(function() r:openFiles('r') end))
assert(r.mode=='none' and memory[0x191de0c]==777); r:reset()
failPath=r.rngFileName
assert(not pcall(function() r:openFiles('w') end))
assert(r.mode=='none' and not files[r.commandsFileName]); allClosed()
''')

    def test_preserves_local_player(self):
        self.check('''
local r=fixture('player'); memory[0x191de0c]=777; memory[0x01a275dc]=3
r:openFiles('r'); r:reset()
assert(memory[0x191de0c]==777 and memory[0x01a275dc]==3)
''')

    def test_real_init_callbacks_return_register_changes(self):
        self.check('''
package.loaded['code/native']={profile={name='SHC'},verify=function() end,addr=function(a) return a end}
local sites=require('tests/fixtures/engine-sites').SHC
for _,key in ipairs({'maintenance','world'}) do
 local site=require('tests/fixtures/maintenance-sites').SHC[key]
 core.writeBytes(site.address,site.bytes)
end
for _,site in pairs(sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
-- This test exercises lifecycle callback routing; binding resolution is covered
-- separately with relocated fixtures and the actual native images/UI owner.
require('code/ui-sites').resolve=function()
 local result=dofile(source_root..'/tests/fixtures/ui-sites.lua').SHC
 for _,site in pairs(result) do core.writeBytes(site.address,site.bytes) end
 local b=result.buildingAndStatus.bytes
 result.window={value=b[3]+b[4]*256+b[5]*65536+b[6]*16777216-0x5c}
 return result
end
for _,site in ipairs(require('code/scoped-sites').SHC) do core.writeBytes(site.address,site.bytes) end
for _,site in pairs(require('code/network-sites').SHC) do core.writeBytes(site.address,site.bytes) end
local history=require('code/history-sites').SHC
for _,name in ipairs({'prepareList','prepare','action','frame','helpText'}) do local s=history[name]; core.writeBytes(s.address,s.bytes) end
for _,s in ipairs(history.operands) do core.writeBytes(s.address,s.bytes) end
core.writeBytes(0x4d1700,{139,68,36,4,163,88,86,223,0}); core.writeBytes(0x4d172a,{232})
local result=require('code/match-results').sites.SHC; core.writeBytes(result.address,result.bytes)
local world=require('code/world-hash-sites').SHC; core.writeBytes(world.address,world.bytes)
core.hookCode=function() return function() return 0 end end
core.writeString=function() end
core.callTo=function() return {} end
core.calculateCodeSize=function(code) return #code+4 end
package.loaded['code/sessions']={captureSettings=function() end}
modules={ui={access=function() return {manager={lookupMenu=function(id) return 0x90000+id*100 end}} end},
 ['map-extensions']=mapSaveOwner,protocol=commandOwner,
 winProcHandler={cinterface=function() return {RegisterProc=101,CallNextProc=102} end},
 cffi={cffi=function() return {tonumber=tonumber,cast=function(_,v) return v end} end}}
local module=dofile(source_root..'/init.lua')
module:enable({rngLogMethod='trace',useFixedSeed=true,fixedSeed=123})
assert(core.readInteger(module.recorder.engine.scope)==0)
assert(callbacks[0x46a74a]==nil) -- seed changes live inside the native scope gate
-- Session playback keeps the native single-player identity path intact.
assert(callbacks[0x47eaf0]==nil)
''')

    def test_native_verification_fails_before_installing_hooks(self):
        self.check('''
local module=dofile(source_root..'/init.lua')
assert(module:enable({}).status=='disabled')
assert(next(callbacks)==nil)
''')


if __name__ == '__main__':
    unittest.main()
