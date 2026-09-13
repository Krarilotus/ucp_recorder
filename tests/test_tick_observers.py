"""Public diagnostic listeners do not mutate or break the recording session."""
import unittest
import test_recorder as fixture


class TickObserverTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
observers=require('code/tick-observers').new()
reads=0; tick=10; resources={12,34}; seen={}
r={active=true,status='recording',manifest={id='recording',variant='SHC',snapshotHash='save',settingsHash='settings'},
 engine={singlePlayer=function()return true end,tick=function()return tick end,
 resourceState=function()reads=reads+1;return resources end}}
''')

    def test_no_listener_does_no_work_and_context_is_not_recorder_state(self):
        self.check('''
observers:dispatch(r);assert(reads==0)
observers:register(function(c)c.resources[1]=99;c.manifest.id='changed';c.active=false end)
observers:register(function(c)seen[#seen+1]=c end)
observers:dispatch(r)
assert(reads==1 and resources[1]==12 and r.manifest.id=='recording' and r.active)
assert(seen[1].resources[1]==12 and seen[1].manifest.id=='recording' and seen[1].active)
assert(seen[1].tick==10 and seen[1].engine==nil)
''')

    def test_failure_is_removed_without_suppressing_other_listeners(self):
        self.check('''
local failures=0
observers:register(function()failures=failures+1;error('diagnostic failure')end)
local token=observers:register(function(c)seen[#seen+1]=c.tick end)
observers:dispatch(r);tick=11;observers:dispatch(r)
assert(failures==1 and #seen==2 and seen[2]==11 and r.status=='recording')
observers:remove(token);tick=12;observers:dispatch(r);assert(#seen==2)
''')

    def test_stop_notification_and_subscription_changes_are_safe(self):
        self.check('''
local first,second
first=observers:register(function(c)
 seen[#seen+1]=c
 observers:remove(first);observers:remove(second)
 observers:register(function(next)seen[#seen+1]=next end)
end)
second=observers:register(function()error('removed listener must not run')end)
observers:dispatch(r);assert(#seen==1)
r.active=false;r.status='idle';observers:dispatch(r)
assert(#seen==2 and seen[2].active==false and #seen[2].resources==0 and reads==1)
''')


if __name__ == '__main__':
    unittest.main()
