"""Sparse native work must keep the same command/clock boundary on replay."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class MaintenanceJournalTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.globals().source_root = ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
work=require('code/maintenance-journal')
local encoded={}
json={encode=function(_,row)
  encoded[#encoded+1]=row; return tostring(#encoded)
end,decode=function(_,line) return assert(encoded[tonumber(line)]) end}
now=100; calls={}; rows={}; reads=0; pending=0
session={active=true,status='recording',manifest={startTick=100,lastTick=200,
 commandCount=0,phaseProfile=work.PROFILE},engine={tick=function() return now end,journal={executed=0}},
 phaseNative={take=function() local n=pending; pending=0; return n end,
 replay=function(_,kind,count) calls[#calls+1]={now,session.engine.journal.executed,kind,count} end}}
session.phaseFile={write=function(_,line) rows[#rows+1]=line; return true end,
 flush=function() return true end,read=function() reads=reads+1; return rows[reads] end}
function append(time,commands,kind,count)
 rows[#rows+1]=json:encode({time=time,commands=commands,kind=kind,count=count})
end
''')

    def test_sparse_capture_preserves_work_between_commands_at_same_tick(self):
        self.lua.execute('''
work.capture(session); assert(#rows==0)
pending=37576; work.capture(session)
session.manifest.commandCount=1
pending=2; work.capture(session); work.write(session,2,1)
session.manifest.commandCount=2; now=101
pending=7; work.capture(session)
session.status='playing'; now=100
work.play(session)
assert(#calls==1 and calls[1][4]==37576)
local prefetched=reads; work.play(session); assert(reads==prefetched)
session.engine.journal.executed=1; work.play(session)
assert(#calls==3 and calls[2][3]==1 and calls[2][4]==2 and calls[3][3]==2)
session.engine.journal.executed=2; work.play(session); assert(#calls==3)
now=101; work.play(session); work.finished(session)
assert(#calls==4 and calls[4][4]==7)
local atEnd=reads
for i=1,100 do work.play(session); work.finished(session) end
assert(reads==atEnd,'Completed work stream must not read again on every tick')
''')

    def test_missed_boundary_or_trailing_work_fails_before_simulation(self):
        self.lua.execute('''
session.manifest.commandCount=2
append(100,1,1,3)
assert(not pcall(work.finished,session))
now=101
assert(not pcall(work.play,session) and #calls==0)
now=100; session.engine.journal.executed=2
assert(not pcall(work.play,session) and #calls==0)
''')

    def test_preflight_rejects_invalid_and_reordered_events(self):
        self.lua.execute('''
session.manifest.commandCount=2
local function check(events)
 return pcall(work.preflight,session.manifest,'root',function(_,_,visit)
   for _,event in ipairs(events) do visit(event) end
 end)
end
local function event(time,commands,kind,count)
 return {time=time,commands=commands,kind=kind,count=count}
end
assert(check({event(100,0,1,5),event(100,1,2,1),event(200,2,1,9)}))
for _,bad in ipairs({event(99,0,1,1),event(201,0,1,1),event(100,3,1,1),
 event(100,0,0,1),event(100,0,3,1),event(100,0,1,0),event(100,0,1,0.5),
 event(100,0,1,2147483648)}) do assert(not check({bad})) end
assert(not check({event(101,0,1,1),event(100,0,1,1)}))
assert(not check({event(100,2,1,1),event(101,1,1,1)}))
''')

    def test_optional_legacy_file_and_inactive_capture_do_no_work(self):
        self.lua.execute('''
session.manifest.phaseProfile=nil
work.play(session); work.finished(session)
work.preflight(session.manifest,'unused',function() error('unexpected file scan') end)
for _,status in ipairs({'idle','armed','playing','error'}) do
 session.status=status; pending=12; work.capture(session); assert(pending==12)
end
session.status='recording'; session.active=false; work.capture(session)
assert(pending==12 and #rows==0 and #calls==0 and reads==0)
''')

    def test_seal_keeps_only_the_verified_prefix_and_hashes_replacement(self):
        self.lua.execute('''
session.manifest.commandCount=1; session.manifest.lastTick=150
append(100,0,1,3); append(150,1,2,1); append(151,2,1,7)
local output,closed={},0
local input={lines=function() local i=0; return function() i=i+1; return rows[i] end end,
 close=function() closed=closed+1; return true end}
io.open=function(path,mode)
 if mode=='r' then return input end
 return {write=function(_,line) output[#output+1]=line; return true end,
 close=function() closed=closed+1; return true end}
end
local replaced=false
package.loaded['code/native-hash']={file=function(path)
 assert(replaced and path=='root/maintenance.jsonl'); return 'digest'
end}
work.seal(session.manifest,'root',function(source,target)
 assert(closed==2 and source==target..'.tmp'); replaced=true
end)
assert(#output==2 and #rows==3 and session.manifest.phaseHash=='digest')
''')


if __name__ == '__main__':
    unittest.main()
