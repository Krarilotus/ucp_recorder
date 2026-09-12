import unittest
import test_sessions as fixture


class InputStateTests(unittest.TestCase):
    setUp = fixture.SessionTests.setUp
    check = fixture.SessionTests.check

    def test_recording_is_live_but_every_playback_status_is_blocked(self):
        self.check('''
local r=session(); local input=r.input
assert(not input:read().blocked)
r:startRecording(); r:activateRecording()
assert(not input:read().blocked and input:read().mode=='record')
for _,status in ipairs({'loading','playing','paused','finished','error'}) do
 r.mode='play'; r.status=status; r.active=status=='playing'
 assert(input:read().blocked)
end
r.mode='none'; r.engine.loading=true; assert(input:read().blocked)
r.engine.loading=false; r.engine.offline={}; assert(input:read().blocked)
r.engine.offline=nil; assert(not input:read().blocked)
''')

    def test_nested_restore_never_reopens_live_input_between_reset_and_load(self):
        self.check('''
local r=session(); local input=r.input; local seen={}
local stop=input:observe(function()
 local state=input:read(); seen[#seen+1]=state
 if #seen>1 then assert(state.generation>seen[#seen-1].generation) end
end)
r.mode='play'; r.status='finished'
input:transition(function()
 r:reset()
 assert(r.mode=='none' and input:read().blocked)
 input:transition(function() r.mode='play'; r.status='playing' end)
end)
assert(#seen==6)
for _,state in ipairs(seen) do assert(state.blocked) end
r:reset(); assert(not input:read().blocked)
stop(); local count=#seen; r:reset(); assert(#seen==count)
''')

    def test_load_boundary_cancels_before_reset_and_stays_blocked_through_reader(self):
        self.check('''
local r=session(); local input=r.input; engine.sites={packager=42}
engine.loadedSkirmish=function() return true end
local lifecycle=require('code/load-lifecycle').new(r)
local cancelled=false
input:observe(function() cancelled=true end)
local reset=r.reset
r.reset=function(self) assert(cancelled and input:read().blocked); reset(self) end
lifecycle:begin(); assert(input:read().blocked)
lifecycle:readComplete(42); assert(input:read().blocked)
lifecycle:finish(); assert(not input:read().blocked and r.status=='armed')
''')

    def test_failed_transition_and_observer_fail_closed_without_skipping_other_consumers(self):
        self.check('''
local r=session(); local input=r.input; local cancelled=false; local mutated=false
input:observe(function() error('consumer cancellation failed') end)
input:observe(function() cancelled=true end)
assert(not pcall(input.transition,input,function() mutated=true end))
assert(cancelled and not mutated and input:read().blocked)
local other=session().input
assert(not pcall(other.transition,other,function() error('load failed') end))
assert(other:read().blocked)
''')
