import unittest
import test_recorder as fixture


class PreparationTaskTests(unittest.TestCase):
    setUp = fixture.RecorderTests.setUp
    check = fixture.RecorderTests.check

    def test_budget_yields_without_consuming_the_entire_task(self):
        self.check('''
local Task=require('code/preparation-task'); local now=4294967290; local completed=0
local task=Task.new(function(progress)
 for i=1,100 do progress('Checking'); completed=completed+1; now=(now+4)%4294967296 end
 return {verified=true}
end,function() return now end)
task:step(); assert(task.status=='pending' and completed==3)
while task.status=='pending' do task:step() end
assert(completed==100 and task.status=='ready' and task.result.verified and not task.thread)
task:step(); assert(completed==100)
''')

    def test_cancellation_unwinds_the_owner_and_never_returns_prepared_state(self):
        self.check('''
local Task=require('code/preparation-task'); local closed=false; local time=0
local task=Task.new(function(progress)
 local ok,reason=pcall(function() progress('Open file'); error('must not finish') end)
 closed=true; assert(ok,reason); return 'unsafe result'
end,function() time=time+20; return time end)
task:step(); assert(task.status=='pending' and not closed)
task:cancel(); task:step()
assert(closed and task.status=='cancelled' and not task.result and not task.thread)
''')

    def test_failure_and_cancel_before_start_do_not_load(self):
        self.check('''
local Task=require('code/preparation-task')
for _,cancel in ipairs({false,true}) do
 local started=false
 local task=Task.new(function(progress)
  progress('Checking'); started=true; error('damaged tail')
 end,function() return 0 end)
 if cancel then task:cancel() end
 task:step()
 assert(task.status==(cancel and 'cancelled' or 'failed') and not task.result)
 assert(started==not cancel)
end
''')

    def test_fast_progress_does_not_create_artificial_frame_delays(self):
        self.check('''
local Task=require('code/preparation-task'); local now=0; local checked=0
local task=Task.new(function(progress)
 for i=1,30000 do
  checked=checked+1
  if i%3000==0 then now=now+1 end
  progress('Checking')
 end
 return {checked=checked}
end,function() return now end)
task:step()
assert(task.status=='ready' and task.result.checked==30000)
assert(task.workMs==10 and task.elapsedMs==10)
''')
