import unittest
import test_recorder as fixture


class CommandJournalTests(unittest.TestCase):
    check = fixture.RecorderTests.check
    setUp = fixture.RecorderTests.setUp

    def test_order_actor_payload_and_tick_are_verified(self):
        self.check('''
local Journal=require('code/command-journal')
for _,key in ipairs({'player','time','commandCategory','size','data'}) do
 local j=Journal.new(); local c=command(); j:queue(0,c)
 if key=='data' then c[key]='FF' else c[key]=c[key]+1 end
 assert(not pcall(function() j:before(0,c) end))
 assert(j:pending() and j.executed==0)
end
local j=Journal.new(); j:queue(199,command()); j:queue(0,command())
assert(not pcall(function() j:before(0,command()) end))
assert(not pcall(function() j:before(1,command()) end))
local first=j:before(199,command()); j:after(199,first)
local second=j:before(0,command()); j:after(0,second)
assert(not j:pending() and j.executed==2)
''')

    def test_ownership_survives_caller_mutation_and_rejects_reuse(self):
        self.check('''
local j=require('code/command-journal').new(); local c=command()
j:queue(1,c); c.data='FF'
assert(not pcall(function() j:queue(1,command()) end))
local entry=j:before(1,command()); j:after(1,entry)
assert(not pcall(function() j:after(1,entry) end))
j:queue(1,command()); assert(j:pending() and j.executed==1)
''')
