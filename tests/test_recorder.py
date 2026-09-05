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
memory, bytes, callbacks, files, handles, scheduled = {}, {}, {}, {}, {}, 0
local nextAddress = 0x10000000
core = {
  allocate = function(size) local a=nextAddress; nextAddress=a+size+16; return a end,
  readInteger = function(a) return memory[a] or 0 end,
  writeInteger = function(a,v) memory[a]=v end,
  readSmallInteger = function(a) return memory[a] or 0 end,
  writeSmallInteger = function(a,v) memory[a]=v end,
  readBytes = function(a,n) local t={}; for i=1,n do t[i]=bytes[a+i-1] or 0 end; return t end,
  writeBytes = function(a,t) for i,v in ipairs(t) do bytes[a+i-1]=v end end,
  writeCode = function() end, copyMemory = function() end,
  AssemblyLambda = function(s,vars) return {assembly=s, variables=vars} end,
  detourCode = function(f,a) callbacks[a]=f end, insertCode = function() end,
  allocateCode = function() nextAddress=nextAddress+128; return nextAddress end,
  exposeCode = function() return function() scheduled=scheduled+1 end end,
}
utils = {createLuaFunctionWrapper=function() return 0 end}
json = {encode=function(_,value) return value end, decode=function(_,value) return value end}
io.open = function(path,mode)
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
Recorder = require('code/recorder')
function fixture(name)
  local r=Recorder:new({name=name,rngLogMethod='trace'})
  files[r.commandsFileName]={}
  files[r.rngFileName]={}
  files[r.infoFileName]={{gameType=0,mapSeed=1,matchSeed=1,RNGvalue1=1,RNGvalue2=1,RNGindex1=1,RNGindex2=1}}
  return r
end
function command(tick) return {time=tick or 1,commandCategory=28,player=1,size=1,data='01'} end
function allClosed() for _,h in ipairs(handles) do assert(h.closed) end end
''')

    def check(self, script):
        self.lua.execute(script)

    def test_reset_drops_prefetch_and_is_idempotent(self):
        self.check('''
local r=fixture('cache'); files[r.commandsFileName]={command(685)}
r:startPlayback(); assert(r:peekCommand().time==685); r.cachedRNG={time=999}
r:stopPlayback(); r:reset(); files[r.commandsFileName]={command(114)}
r:startPlayback(); assert(r:consumeSavedCommand().time==114 and not r.cachedRNG)
r:stopPlayback(); allClosed()
''')

    def test_missing_and_partial_files_do_not_commit_state(self):
        self.check('''
local r=Recorder:new({name='missing'}); memory[0x191de0c]=777
assert(not pcall(function() r:startPlayback() end))
assert(r.mode=='none' and memory[0x191de0c]==777); r:reset()
failPath=r.rngFileName
assert(not pcall(function() r:startRecording() end))
assert(r.mode=='none' and not files[r.commandsFileName]); allClosed()
''')

    def test_preserves_local_player(self):
        self.check('''
local r=fixture('player'); memory[0x191de0c]=777; memory[0x01a275dc]=3
r:startPlayback(); r:stopPlayback()
assert(memory[0x191de0c]==777 and memory[0x01a275dc]==3)
''')

    def test_instances_own_buffers(self):
        self.check('local a=fixture("a"); local address=a.commandDataAddress; local b=fixture("b"); assert(a.commandDataAddress==address and address~=b.commandDataAddress)')

    def test_late_malformed_command_is_rejected_before_start(self):
        self.check('''
local r=fixture('late'); local bad=command(100); bad.data='XX'
files[r.commandsFileName]={command(1),bad}
assert(not pcall(function() r:startPlayback() end)); assert(r.mode=='none'); allClosed()
''')

    def test_invalid_packets_never_reach_native_boundary(self):
        self.check('''
local r=fixture('payload'); r._scheduleCommand=function() scheduled=scheduled+1 end
for _,change in ipairs({{size=1261,data=string.rep('AA',1261)}, {size=1,data='0102'},
 {data='GG'}, {commandCategory=999}, {player=0}, {time=0}, {time=1.5}}) do
  local c=command(); for k,v in pairs(change) do c[k]=v end
  assert(not pcall(function() r:scheduleCommand(c) end))
end
assert(scheduled==0)
r:scheduleCommand(command()); assert(scheduled==1)
assert(bytes[r.commandDataAddress]==1 and bytes[r.commandDataAddress+1259]==0)
''')

    def test_rng_value_index_and_tick_mismatches_are_retained(self):
        for key in ('rng1', 'rng2', 'index1', 'index2', 'time'):
            with self.subTest(key=key):
                self.lua.globals().different_key = key
                self.check('''
local r=fixture('rng'); r.mode='play'; memory[r.rngRecorderState]=2
memory[0x2000]=0x420f76
r.cachedRNG={time=0,rng1=0,rng2=0,index1=0,index2=0,extra={ra2=0x420f76}}
r.cachedRNG[different_key]=100
r:syncCheck({ESP=0x2000},2)
assert(r.firstDesync and r.firstDesync.reason==different_key)
assert(memory[r.commandRecorderState]==0 and memory[r.rngRecorderState]==0)
''')

    def test_real_init_callbacks_return_register_changes(self):
        self.check('''
package.loaded['code/native']={profile={name='SHC'},verify=function() end,addr=function(a) return a end}
local sites=require('code/engine-sites').SHC
for _,site in pairs(sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
core.hookCode=function() return function() return 0 end end
core.writeString=function() end
core.callTo=function() return {} end
package.loaded['code/sessions']={captureSettings=function() end}
local module=dofile(source_root..'/init.lua')
module:enable({rngLogMethod='trace',useFixedSeed=true,fixedSeed=123})
assert(callbacks[0x46a74a]({EAX=456}).EAX==123)
-- Session playback keeps the native single-player identity path intact.
assert(callbacks[0x47eaf0]==nil)
''')

    def test_native_verification_fails_before_installing_hooks(self):
        self.check('''
local module=dofile(source_root..'/init.lua')
assert(not pcall(function() module:enable({}) end))
assert(next(callbacks)==nil)
''')


if __name__ == '__main__':
    unittest.main()
