import unittest
import test_recorder as fixture


class SnapshotCadenceTests(unittest.TestCase):
    check=fixture.RecorderTests.check
    setUp=fixture.RecorderTests.setUp

    def test_elapsed_years_start_at_loaded_date_not_round_calendar_year(self):
        self.check('''
local clock=require('code/snapshot-cadence')
local origin=clock.month(1184,3)
for _,interval in ipairs({clock.LOCAL_MONTHS,clock.EMBEDDED_MONTHS}) do
 local c=clock.new(origin,interval)
 assert(not c:due(origin) and not c:due(origin+interval-1))
 assert(c:due(origin+interval)); c:commit(origin+interval)
 assert(not c:due(origin+interval) and not c:due(origin-100))
 assert(c:due(origin+interval*2))
end
assert(clock.month(1184,11)+1==clock.month(1185,0))
assert(not pcall(clock.month,1184,12))
''')

    def test_300_years_yields_12_embedded_points_and_300_local_points(self):
        self.check('''
local clock=require('code/snapshot-cadence')
for _,row in ipairs({{clock.LOCAL_MONTHS,300},{clock.EMBEDDED_MONTHS,12}}) do
 local c=clock.new(12000,row[1]); local count=0
 for month=12000,15600 do
  if c:due(month) then c:commit(month); count=count+1 end
 end
 assert(count==row[2])
end
''')

    def test_failed_capture_remains_due_and_calendar_jump_does_not_backfill_fake_worlds(self):
        self.check('''
local c=require('code/snapshot-cadence').new(100,12)
assert(c:due(112) and c:due(112)) -- No commit on capture failure.
c:commit(149); assert(c.nextMonth==160 and not c:due(149))
assert(not pcall(function() c:commit(150) end))
''')
