import unittest
import test_recorder as fixture


class AttributionTests(unittest.TestCase):
    check = fixture.RecorderTests.check

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
engine={rng=0x2000,tick=function() return now end,singlePlayer=function() return single end,
 rngState=function() return {10,20,30,40} end}
realNative.profile.name='SHC'; realNative.profile.sha256='test-executable'
Attribution=require('code/rng-attribution'); trace=Attribution.new(engine)
manifest={id='test'}; trace:observe('begin',manifest,'record')
assert(trace.file and encoded[1].kind=='header')
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
