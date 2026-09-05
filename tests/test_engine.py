import unittest
import test_recorder as fixture


class EngineTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
Engine=require('code/engine')
local sites=require('code/engine-sites').SHC
engine=Engine.new(sites)
core.readByte=function(a) return bytes[a] or 0 end
core.writeByte=function(a,v) bytes[a]=v end
core.writeString=function(a,s)
 for i=1,#s do bytes[a+i-1]=s:byte(i) end; bytes[a+#s]=0
end
''')

    def test_failed_save_restores_exact_filename_and_progress_callback(self):
        self.check('''
local s=engine.sites
local name=s.resources+0x7aee0+1001
for i=0,1001 do bytes[name+i]=42 end
memory[s.resources+0xbc4]=14; memory[s.packager+0x20]=12345
engine.saveNative=function() error('injected save failure') end
assert(not pcall(function() engine:saveSnapshot('ucp/replays/test/start.sav') end))
assert(memory[s.resources+0xbc4]==14 and memory[s.packager+0x20]==12345)
for i=0,1001 do assert(bytes[name+i]==42) end
''')

    def test_failed_load_restores_selection_and_scoped_filename_override(self):
        self.check('''
local state=engine.sites.menuText
for _,offset in ipairs({0x58,0x7c,0x80,0x884}) do memory[state+offset]=offset end
engine.loadNative=function()
 assert(engine.loading and engine.overridePath=='test.sav'); error('injected load failure')
end
assert(not pcall(function() engine:loadSnapshot('test.sav') end))
assert(not engine.loading and not engine.overridePath)
for _,offset in ipairs({0x58,0x7c,0x80,0x884}) do assert(memory[state+offset]==offset) end
''')

    def test_full_ring_rejects_write_and_pending_slot_requires_native_completion(self):
        self.check('''
local slot=engine.base+0x3c67c+9
bytes[slot]=1
assert(not pcall(function() engine:scheduleCommand(command()) end)); assert(scheduled==0)
bytes[slot]=10
engine.schedule=function() bytes[slot]=1 end
engine:scheduleCommand(command()); assert(engine:commandsPending())
bytes[slot]=10; assert(engine:commandsPending()) -- native state alone is not execution proof
local entry=engine.journal:before(0,command()); engine.journal:after(0,entry)
assert(not engine:commandsPending())
''')

    def test_native_size_mismatch_clears_slot_and_guard(self):
        self.check('''
core.hookCode=function() return function() return 0 end end
engine:install({mode='play'})
local slot=engine.base+0x3c67c+9
engine.schedule=function()
 bytes[slot]=1; memory[engine.base+0x2d830]=1261
 local result=callbacks[engine.sites.copySize.address]({ESI=engine.base,EDX=engine.buffer})
 assert(result.EAX==0)
end
assert(not pcall(function() engine:scheduleCommand(command()) end))
assert(bytes[slot]==10 and not engine.expectedSize)
''')

    def test_stale_playback_does_not_block_multiplayer_queue(self):
        self.check('''
local hooks={}; local forwarded=0
core.hookCode=function(callback)
 hooks[#hooks+1]=callback; return function() forwarded=forwarded+1; return 42 end
end
engine:install({mode='play'})
memory[engine.base+0x618]=1
assert(hooks[3](engine.base,28)==42 and forwarded==1)
memory[engine.base+0x618]=0
assert(hooks[3](engine.base,28)==0 and forwarded==1)
''')

    def test_multiplayer_cannot_enable_scope_or_be_paused_by_recorder(self):
        self.check('''
memory[engine.base+0x618]=1; memory[engine.sites.paused]=0
engine:pause(); assert(memory[engine.sites.paused]==0)
assert(not pcall(function() engine:setScope(true) end))
engine:setScope(false); assert(memory[engine.scope]==0)
''')

    def command_hooks(self, mode):
        self.check('''
core.hookCode=function() return function() return 0 end end
recorder={active=true,status='recording',mode='record',manifest={player=1,variant='SHC'},commands={}}
function recorder:guard(f)
 local ok,reason=pcall(f); if not ok then self.status='error'; self.error=reason end
 return ok
end
function recorder:onExecutedCommand(c) self.commands[#self.commands+1]=c end
engine:install(recorder)
address=engine.base+0x3c67c
memory[engine.base+0x2d824]=0; memory[address]=10; bytes[address+8]=28
memory[engine.base+engine.sites.actorOffset]=1
memory[0x1fe7da8]=10
memory[engine.base+0x2d830]=1; bytes[engine.buffer]=1; bytes[address+10]=1
function before()
 return callbacks[engine.sites.execute.address]({ESI=engine.base,ECX=0,EDX=999})
end
function after() callbacks[engine.sites.executed.address]({ESI=engine.base}) end
''')
        if mode == 'play':
            self.check("recorder.mode='play'; recorder.status='playing'; engine.journal:queue(0,command(10))")

    def test_capture_observes_execution_not_just_receipt(self):
        self.command_hooks('record')
        self.check('''
callbacks[engine.sites.copySize.address]({ESI=engine.base,EDX=engine.buffer})
assert(#recorder.commands==0)
memory[0x1fe7da8]=12 -- late delivery: record the actual execution boundary
assert(before().EDX==28 and #recorder.commands==0)
after()
assert(#recorder.commands==1 and recorder.commands[1].time==12 and recorder.commands[1].data=='01')
assert(not engine.received[0])
''')

    def test_invalid_captured_size_cannot_reach_native_copy(self):
        self.command_hooks('record')
        self.check('''
memory[engine.base+0x2d830]=1261
local result=callbacks[engine.sites.copySize.address]({ESI=engine.base,EDX=engine.buffer})
assert(result.EAX==0 and recorder.status=='error' and not engine.received[0])
''')

    def test_valid_playback_counts_only_returned_handlers(self):
        self.command_hooks('play')
        self.check('''
assert(before().EDX==28 and engine.journal.executed==0 and engine:commandsPending())
after(); assert(engine.journal.executed==1 and not engine:commandsPending())
''')

    def test_bad_execution_becomes_noop_without_consuming_expected_command(self):
        for corrupt in ("memory[engine.base+engine.sites.actorOffset]=2", "bytes[address+10]=2",
                        "memory[0x1fe7da8]=11", "memory[address]=9", "bytes[address+8]=39"):
            with self.subTest(corrupt=corrupt):
                self.setUp()
                self.command_hooks('play')
                self.check(corrupt)
                self.check('''
assert(before().EDX==0 and recorder.status=='error')
after(); assert(engine:commandsPending() and engine.journal.executed==0)
assert(before().EDX==0) -- later commands in this native batch are suppressed too
''')

    def test_unowned_command_is_rejected_and_multiplayer_dispatch_is_unchanged(self):
        self.command_hooks('play')
        self.check('''
engine:resetCommands(); assert(before().EDX==0)
memory[engine.base+0x618]=1; bytes[address+8]=200
assert(before().EDX==-56) -- original signed-byte conversion, no replay policy in MP
''')

    def test_custom_receive_buffer_is_staged_and_restored_on_success_and_failure(self):
        self.check('''
local address=engine.base+0xcdc
for i=0,1260 do bytes[address+i]=42 end
local c=command(10); c.commandCategory=122; c.size=272; c.data='83000000'..string.rep('00',268)
for _,fail in ipairs({false,true}) do
 engine:resetCommands()
 engine.schedule=function()
  assert(bytes[address]==131 and bytes[address+1]==0 and bytes[address+1259]==0)
  assert(bytes[address+1260]==42)
  if fail then error('receive callback failed') end
 end
 local ok=pcall(function() engine:scheduleCommand(c) end)
 assert(ok~=fail and not engine.expectedSize)
 for i=0,1260 do assert(bytes[address+i]==42) end
 assert(engine:commandsPending()==not fail)
end
''')

    def test_save_wrapper_acceptance_requires_known_extension_and_preserved_tail(self):
        self.check('''
realNative.profile.name='SHC'
for _,site in pairs(engine.sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
assert(Engine.verify())
bytes[engine.sites.save.address]=0xE9
assert(not pcall(Engine.verify))
allActiveExtensions={{name='map-extensions',version='1.0.0'}}; modules={['map-extensions']={}}
assert(Engine.verify())
bytes[engine.sites.save.address+5]=0
assert(not pcall(Engine.verify))
''')

    def test_protocol_must_install_its_dispatch_before_recorder(self):
        self.check('''
realNative.profile.name='SHC'
for _,site in pairs(engine.sites) do
 if type(site)=='table' then core.writeBytes(site.address,site.bytes) end
end
allActiveExtensions={{name='protocol',version='1.0.0'}}
local ok,reason=pcall(Engine.verify)
assert(not ok and tostring(reason):find('after protocol',1,true))
bytes[engine.sites.execute.address+8]=0xE9; assert(Engine.verify())
''')

    def test_resource_snapshot_covers_eight_players_and_ignores_ui_slot_zero(self):
        self.check('''
for _,sites in pairs(require('code/engine-sites')) do
 local e=Engine.new(sites)
 for player=0,8 do
  for resource=0,24 do memory[sites.playerResources+player*0x39f4+resource*4]=player*1000+resource end
 end
 local state=e:resourceState(); assert(#state==200)
 for player=1,8 do
  for resource=0,24 do assert(state[(player-1)*25+resource+1]==player*1000+resource) end
 end
 memory[sites.playerResources+0x39f4+15*4]=-123
 assert(e:resourceState()[16]==-123 and state[16]==1015)
end
''')
