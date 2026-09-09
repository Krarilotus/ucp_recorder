import unittest
import test_recorder as fixture


class AttributionTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def test_fire_caller_inputs_use_existing_observer_without_per_call_writes(self):
        self.check('''
trace:finish('restart')
for _,site in ipairs(require('code/rng-fire-context').SHC) do core.writeBytes(site.address,site.bytes) end
trace:begin(manifest,'record'); assert(encoded[#encoded].fireContext)
local start=writes
memory[100]=0x4052f4
for i,value in ipairs({0x405b27,4,120,160,8,3,100}) do memory[112+i*4]=value end
now=17; trace:rngCall(2,100)
assert(writes==start and #trace.fires==1 and trace.fires[1].caller==0x405b27)
assert(trace.fires[1].player==4 and trace.fires[1].spreadParameter==3 and trace.fires[1].intensity==100)
trace:checkpoint(); assert(#encoded[#encoded].fires==1 and #trace.fires==0)
Attribution.MAX_FIRES=1; trace:observe('rngCall',2,100); trace:observe('rngCall',2,100)
assert(not trace.file and trace.failed:find('fire limit',1,true))
assert(memory[100]==0x4052f4 and memory[140]==100)
''')

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
local directories={}
package.loaded['code/platform']={mkdir=function(path)
 if directories[path] then return false end; directories[path]=true; return true
end}
encoded={}; writes=0; closes=0
json.encode=function(_,value) encoded[#encoded+1]=value; return 'json' end
io.open=function(path)
 return {write=function() writes=writes+1; return true end,flush=function() return true end,
 close=function() closes=closes+1; return true end}
end
now=1; single=true
engine={rng=0x2000,sites={navigationCountdown=0x3000},tick=function() return now end,singlePlayer=function() return single end,
 rngState=function() return {10,20,30,40} end}
realNative.profile.name='SHC'; realNative.profile.sha256='test-executable'
Attribution=require('code/rng-attribution'); trace=Attribution.new(engine)
manifest={id='test'}; trace:observe('begin',manifest,'record')
assert(trace.file and encoded[1].kind=='header')
''')

    def test_tick_return_observations_are_bounded_and_retained_without_rng_calls(self):
        self.check('''
memory[0x3000]=100
trace:observe('afterTick') -- no clock advancement
now=2; trace:observe('afterTick')
now=10; trace:observe('afterTick') -- replacement/other caller, not eight observed steps
assert(writes==1)
trace:observe('checkpoint')
local phase=encoded[2].phase
assert(phase.tickReturns==3 and phase.unclockedReturns==1 and phase.clockJumps==1)
assert(phase.navigationCountdown==100 and memory[0x3000]==100)
single=false; trace:observe('afterTick'); assert(trace.tickReturns==0)
single=true; trace:observe('afterTick'); trace:observe('finish','paused exit')
assert(encoded[3].phase.tickReturns==1 and encoded[3].phase.unclockedReturns==1)
assert(encoded[4].kind=='end')
trace:observe('afterTick'); assert(not trace.file)
''')

    def test_calls_are_buffered_normalized_and_flushed_at_boundary(self):
        self.check('''
trace.returnAddresses={[0xf0000000]=0x404f16}
memory[100]=-268435456; now=17
trace:observe('rngCall',2,100); trace:observe('rngCall',2,100)
memory[100]=0x46a805; now=18; trace:observe('rngCall',1,100)
assert(writes==1 and trace.count==3)
now=64; trace:observe('checkpoint')
local entry=encoded[2]
assert(entry.count==3 and entry.fromTick==1 and entry.time==64)
assert(entry.calls[1].stream==1 and entry.calls[2].returnAddress==0x404f16)
assert(entry.calls[2].count==2 and entry.calls[2].firstTick==17 and entry.calls[2].lastTick==17)
assert(trace.count==0 and trace.callers==0)
trace:observe('finish','failed replay')
assert(encoded[3].kind=='end' and not trace.file and closes==1)
''')

    def test_new_attempt_does_not_overwrite_and_inactive_or_multiplayer_calls_are_ignored(self):
        self.check('''
local first=trace.path
single=false; trace:observe('rngCall',1,100); assert(trace.count==0)
single=true; trace:observe('finish','done')
trace:observe('rngCall',1,100); assert(trace.count==0)
trace:observe('begin',manifest,'record')
assert(trace.path~=first and trace.file and trace.count==0)
''')

    def test_io_and_limits_disable_only_observation_and_allow_next_attempt(self):
        for failure in ('write', 'flush', 'close', 'callers', 'bytes'):
            with self.subTest(failure=failure):
                self.setUp()
                self.lua.globals().failure = failure
                self.check('''
if failure=='callers' then
 Attribution.MAX_CALLERS=1
 memory[100]=1; trace:observe('rngCall',1,100)
 memory[100]=2; trace:observe('rngCall',1,100)
else
 if failure=='bytes' then trace.bytes=Attribution.MAX_BYTES
 else trace.file[failure]=function() return nil,'disk error' end end
 trace:observe('finish','done')
end
assert(trace.failed and not trace.file and trace.count==0)
trace:observe('rngCall',1,100); assert(trace.count==0)
trace:observe('begin',manifest,'play')
assert(trace.file and not trace.failed)
''')

    def test_order_fingerprint_distinguishes_equal_counts_in_different_order(self):
        self.check('''
memory[100]=10; trace:observe('rngCall',1,100)
memory[100]=20; trace:observe('rngCall',2,100)
local first=trace.order
trace:clear()
memory[100]=20; trace:observe('rngCall',2,100)
memory[100]=10; trace:observe('rngCall',1,100)
assert(first~=trace.order and trace.count==2)
''')

    def test_spawn_context_is_optional_bounded_and_read_only(self):
        self.check('''
assert(not trace.spawnProfile and encoded[1].spawnContext==false)
local context=require('code/rng-spawn-context')
local profile=context.SHC
core.writeBytes(profile.entry,{83,139,217,185,1,0,0,0,87,139,249})
core.writeBytes(profile.call,profile.callBytes)
trace:observe('finish','setup'); trace:observe('begin',manifest,'record')
assert(trace.spawnProfile and encoded[#encoded].spawnContext==true)
memory[100]=profile.call+5
local args={-268435456,2,4,120,160,8,1}
for i,value in ipairs(args) do memory[116+i*4]=value end
now=50; trace:observe('rngCall',2,100)
assert(trace.spawns[1].caller==0xf0000000 and trace.spawns[1].player==2)
assert(trace.spawns[1].microX==120 and trace.spawns[1].unitType==1)
assert(memory[120]==-268435456 and memory[144]==1)
now=64; trace:observe('checkpoint')
assert(#encoded[#encoded].spawns==1 and #trace.spawns==0)
Attribution.MAX_SPAWNS=1
trace:observe('rngCall',2,100); trace:observe('rngCall',2,100)
assert(trace.failed and not trace.file and memory[144]==1)
''')
