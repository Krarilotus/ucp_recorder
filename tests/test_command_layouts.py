import unittest
import test_recorder as recorder_fixture
import test_session_files as file_fixture


class CommandLayoutTests(unittest.TestCase):
    setUp = recorder_fixture.RecorderTests.setUp

    def test_remaining_gameplay_layouts_reject_short_and_long_payloads(self):
        self.lua.execute('''
local validate=require('code/validation').sessionCommand
for _,variant in ipairs({'SHC','Extreme'}) do
 for category,size in pairs({[33]=7,[37]=7,[72]=4,[73]=2,[74]=6,
                            [75]=4,[76]=1213,[79]=1,[86]=3,[97]=4}) do
  local c={commandCategory=category,player=1,time=10,size=size,data=string.rep('A5',size)}
  local m={player=1,variant=variant}
  assert(validate(c,m)==c)
  for _,wrong in ipairs({size-1,size+1}) do
   c.size=wrong; c.data=string.rep('A5',wrong)
   local ok,err=pcall(validate,c,m)
   assert(not ok and err:find('payload size',1,true))
  end
 end
end
''')

    def test_native_io_network_and_removed_commands_remain_excluded(self):
        self.lua.execute('''
local validate=require('code/validation').sessionCommand
for _,variant in ipairs({'SHC','Extreme'}) do
 for category,size in pairs({[8]=0,[30]=0,[32]=0,[39]=75,[54]=8,[77]=4,[83]=3}) do
  local c={commandCategory=category,player=1,time=10,size=size,data=string.rep('00',size)}
  local ok,err=pcall(validate,c,{player=1,variant=variant})
  assert(not ok and err:find('Unsupported replay command category',1,true))
 end
end
''')

    def test_rally_points_use_five_byte_native_layout_on_both_variants(self):
        self.lua.execute('''
local validate=require('code/validation').sessionCommand
for _,variant in ipairs({'SHC','Extreme'}) do
 local m={player=1,variant=variant}
 local c={commandCategory=102,player=1,time=10,size=5,data='280A001400'}
 assert(validate(c,m)==c) -- cathedral category, x=10, y=20
 for _,size in ipairs({0,1,4,6,1260}) do
  c.size=size; c.data=string.rep('00',size)
  local ok,err=pcall(validate,c,m)
  assert(not ok and err:find('payload size',1,true))
 end
end
''')

    def test_native_sizes_reject_truncation_extension_and_immediate_chat(self):
        self.lua.execute('''
local validate=require('code/validation').sessionCommand
local manifest={player=1,variant='SHC'}
for _,size in ipairs({0,1,9,11,1260}) do
 local c={commandCategory=28,player=1,time=1,size=size,data=string.rep('00',size)}
 local ok,err=pcall(validate,c,manifest)
 assert(not ok and err:find('payload size',1,true))
end
local c={commandCategory=28,player=1,time=1,size=10,data=string.rep('00',10)}
assert(validate(c,manifest)==c)
c.commandCategory=14; c.size=544; c.data=string.rep('00',544)
local ok,err=pcall(validate,c,manifest)
assert(not ok and err:find('Unsupported replay command category 14',1,true))
''')

    def test_unit_selection_and_tactical_powers_require_the_recorded_variant_layout(self):
        self.lua.execute('''
local validate=require('code/validation').sessionCommand
for _,case in ipairs({{'SHC',402},{'Extreme',1252}}) do
 local c={commandCategory=16,player=1,time=1,size=case[2],data=string.rep('00',case[2])}
 assert(validate(c,{player=1,variant=case[1]})==c)
 local other=case[1]=='SHC' and 'Extreme' or 'SHC'
 assert(not pcall(validate,c,{player=1,variant=other}))
end
local c={commandCategory=119,player=1,time=1,size=8,data=string.rep('00',8)}
assert(validate(c,{player=1,variant='Extreme'})==c)
assert(not pcall(validate,c,{player=1,variant='SHC'}))
assert(not pcall(validate,c,{player=1,variant='unknown'}))
''')


class LayoutFileTests(unittest.TestCase):
    setUp = file_fixture.SessionFileTests.setUp

    def test_valid_hash_cannot_make_a_wrong_native_layout_pass_preflight(self):
        self.lua.execute('''
local m=recording(); store.finish(m)
local path=store.path(m.id)..'/stream-commands.json'
-- Intact JSON, timeline, actor and checksum, but not the native building payload.
store.write(path,json:encode({commandCategory=28,player=1,time=10,size=1,data='01'})..'\\n')
m.commandsHash=sha.sha256(store.read(path))
local ok,err=pcall(store.preflight,m)
assert(not ok and err:find('payload size',1,true))
''')

    def test_old_rng_profile_is_rejected_before_native_load(self):
        self.lua.execute('''
local m=recording(); store.finish(m)
assert(m.simulationProfile=='recorder-sp-v10')
m.simulationProfile='recorder-sp-v9'; store.save(m)
local ok,err=pcall(store.load,m.id,profile)
assert(not ok and err:find('different simulation profile',1,true))
''')
