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
bytes[slot]=10; assert(not engine:commandsPending())
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
