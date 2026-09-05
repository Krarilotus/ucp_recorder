"""Replay dispatch batches: order, admission, isolation and cancellation."""
import unittest
import test_engine


class DispatchPipelineTests(unittest.TestCase):
    check = test_engine.EngineTests.check

    def setUp(self):
        test_engine.EngineTests.setUp(self)
        self.check('''
hooks={}; forwarded=0
core.hookCode=function(callback,address)
 hooks[address]=callback
 return function() forwarded=forwarded+1; return 42 end
end
recorder={mode='play',status='playing',active=true,manifest={player=1,variant='SHC'}}
function recorder:guard(callback)
 local ok,reason=pcall(callback)
 if not ok then self.status='error'; self.error=reason; engine:abortPlayback() end
 return ok
end
function recorder:feed() end
engine:install(recorder)
engine.schedule=simulatedSchedule
memory[engine.base+engine.sites.actorOffset+4]=1
memory[0x1fe7da8]=10
function selectCommands() return hooks[engine.sites.select.address](engine.base) end
function finishBatch()
 local count=memory[engine.base+engine.sites.selectedCountOffset]
 for i=0,count-1 do
  local slot=memory[engine.base+engine.sites.selectedOffset+i*8]
  local source=engine.journal.slots[slot]
  engine.journal:before(slot,source.command); engine.journal:after(slot,source)
  bytes[engine.base+0x3c67c+slot*1272+9]=10
 end
end
''')

    def test_wrapped_slots_follow_recorded_order_for_multiple_batches(self):
        self.check('''
memory[engine.base+engine.sites.writeIndexOffset]=199
for tick=10,15 do
 memory[0x1fe7da8]=tick
 for i=1,100 do engine:scheduleCommand(command(tick)) end
 assert(selectCommands()==1)
 for i=0,99 do
  assert(memory[engine.base+engine.sites.selectedOffset+i*8]==(199+(tick-10)*100+i)%200)
  assert(memory[engine.base+engine.sites.selectedOffset+i*8+4]==1)
 end
 finishBatch()
end
assert(engine.journal.executed==600 and not engine:commandsPending())
assert(selectCommands()==0 and memory[engine.base+engine.sites.selectedCountOffset]==0)
''')

    def test_future_and_late_commands_do_not_execute_at_another_tick(self):
        self.check('''
engine:scheduleCommand(command(11))
assert(selectCommands()==0 and engine:commandsPending())
memory[0x1fe7da8]=12
assert(selectCommands()==0 and recorder.status=='error' and engine.journal.executed==0)
assert(memory[engine.base+engine.sites.selectedCountOffset]==0)
''')

    def test_session_feeds_and_finishes_across_fast_frames_without_receive_callbacks(self):
        for ticks_per_frame in (1,3,20):
            with self.subTest(ticks_per_frame=ticks_per_frame):
                self.setUp()
                self.lua.globals().ticks_per_frame=ticks_per_frame
                self.check('''
local Session=require('code/session-recorder')
require('code/sessions').write=function() end
sha={sha256=function() return string.rep('a',64) end}
engine.rngData=function() return string.rep('x',0x9c50) end
recorder=Session:new(engine); recorder.mode='play'; recorder.status='playing'; recorder.active=true
recorder.playedCommands=0
recorder.manifest={id='test',player=1,variant='SHC',lastTick=29,commandCount=1600,
 finalRng={0,0,0,0},finalResources=resourceState(),finalRngHash=string.rep('a',64)}
local stream={}; for tick=10,29 do for i=1,80 do stream[#stream+1]=command(tick) end end
local cursor=0
recorder.commandsFile={read=function() cursor=cursor+1; return stream[cursor] end}
engine:install(recorder)
memory[engine.base+engine.sites.writeIndexOffset]=175
local tick=10
while tick<=29 do
 for frameTick=1,ticks_per_frame do
  if tick>29 then break end
  memory[0x1fe7da8]=tick
  assert(selectCommands()==1 and recorder.status=='playing',recorder.error)
  assert(memory[engine.base+engine.sites.selectedCountOffset]==80)
  for i=0,79 do
   local slot=memory[engine.base+engine.sites.selectedOffset+i*8]
   memory[engine.base+0x2d824]=slot; memory[engine.base+engine.sites.actorOffset]=1
   engine:beforeCommand(recorder); engine:afterCommand(recorder)
   bytes[engine.base+0x3c67c+slot*1272+9]=10
  end
  recorder:onTick()
  tick=tick+1
 end
end
assert(recorder.status=='finished' and recorder.playedCommands==1600)
assert(engine.journal.executed==1600 and not engine:commandsPending())
assert(selectCommands()==0)
''')

    def test_whole_batch_is_rejected_before_dispatch_if_any_entry_changed(self):
        for change in ('payload','tick','sender','category','state','untracked'):
            with self.subTest(change=change):
                self.setUp()
                self.lua.globals().change=change
                self.check('''
engine:scheduleCommand(command(10)); engine:scheduleCommand(command(10))
local address=engine.base+0x3c67c+1272
if change=='payload' then bytes[address+10]=99
elseif change=='tick' then memory[address]=9
elseif change=='sender' then memory[address+4]=2
elseif change=='category' then bytes[address+8]=29
elseif change=='state' then bytes[address+9]=10
else bytes[address+1272+9]=1 end
assert(selectCommands()==0 and recorder.status=='error')
assert(engine.journal.executed==0 and memory[engine.base+engine.sites.selectedCountOffset]==0)
''')

    def test_native_selector_runs_unchanged_for_idle_recording_loading_and_multiplayer(self):
        self.check('''
for _,state in ipairs({{'none','idle',0,false},{'record','recording',99,false},
 {'play','playing',0,true},{'play','playing',1,false},{'play','error',2,false}}) do
 recorder.mode=state[1]; recorder.status=state[2]; memory[engine.base+0x618]=state[3]; engine.loading=state[4]
 assert(selectCommands()==42)
end
assert(forwarded==5)
engine.loading=false; memory[engine.base+0x618]=0; recorder.mode='play'
for _,status in ipairs({'loading','finished','error'}) do
 recorder.status=status; assert(selectCommands()==0)
end
assert(forwarded==5)
''')

    def test_enqueue_failures_do_not_leave_a_pending_entry_or_consume_ring_position(self):
        for failure in ('no copy','no advance','wrong data','throw'):
            with self.subTest(failure=failure):
                self.setUp()
                self.lua.globals().failure=failure
                self.check('''
memory[engine.base+engine.sites.writeIndexOffset]=199
local address=engine.base+0x3c67c+199*1272
for i=0,1271 do bytes[address+i]=42 end; bytes[address+9]=10
local old=core.readBytes(address,1272)
engine.schedule=function(...)
 simulatedSchedule(...)
 if failure=='no copy' then engine.copySeen=false
 elseif failure=='no advance' then memory[engine.base+engine.sites.writeIndexOffset]=199
 elseif failure=='wrong data' then bytes[address+10]=99
 else error('native bridge failed after changing the ring') end
end
assert(not pcall(engine.scheduleCommand,engine,command(10)))
assert(memory[engine.base+engine.sites.writeIndexOffset]==199 and not engine:commandsPending())
assert(not engine.expectedSize and not engine.copySeen)
for i=1,1272 do assert(core.readBytes(address,1272)[i]==old[i]) end
''')

    def test_abort_clears_only_replay_owned_slots_and_never_writes_in_multiplayer(self):
        self.check('''
engine:scheduleCommand(command(10)); engine:scheduleCommand(command(10))
local foreign=engine.base+0x3c67c+5*1272+9; bytes[foreign]=1
engine:abortPlayback()
assert(bytes[engine.base+0x3c67c+9]==10 and bytes[engine.base+0x3c67c+1272+9]==10)
assert(bytes[foreign]==1 and memory[engine.base+engine.sites.selectedCountOffset]==0)
memory[engine.base+0x618]=1
core.writeByte=function() error('multiplayer write') end
core.writeInteger=function() error('multiplayer write') end
engine:abortPlayback()
''')

    def test_unknown_ring_state_is_not_treated_as_a_free_slot(self):
        self.check('''
local address=engine.base+0x3c67c+9
for _,state in ipairs({1,9,11,127,128,255}) do bytes[address]=state; assert(not engine:canSchedule()) end
for _,state in ipairs({0,10}) do bytes[address]=state; assert(engine:canSchedule()) end
''')

    def test_multiplayer_or_nested_enqueue_fails_before_writing_native_state(self):
        self.check('''
core.writeBytes=function() error('unexpected native write') end
memory[engine.base+0x618]=1
local ok,reason=pcall(engine.scheduleCommand,engine,command(10))
assert(not ok and tostring(reason):find('requires single%-player'))
memory[engine.base+0x618]=0; engine.expectedSize=4
ok,reason=pcall(engine.scheduleCommand,engine,command(10))
assert(not ok and tostring(reason):find('Nested replay enqueue',1,true))
assert(engine.expectedSize==4 and not engine:commandsPending())
''')
