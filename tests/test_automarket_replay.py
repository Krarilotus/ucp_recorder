import unittest
import test_recorder as fixture


class AutomarketReplayTests(unittest.TestCase):
    check = fixture.RecorderTests.check

    def setUp(self):
        fixture.RecorderTests.setUp(self)
        self.check('''
adapter=require('code/automarket-replay'); validation=require('code/validation')
allActiveExtensions={{name='automarket',version='1.1.0'},{name='protocol',version='1.0.0'},
 {name='map-extensions',version='1.0.0'}}
modules={protocol={getProtocolNumber=function(_,extension,name)
 assert(extension=='automarket' and name=='commitSingle'); return 131
end},['map-extensions']={}}
function marketCommand()
 local payload={}; for i=1,272 do payload[i]=0 end
 payload[1]=131; payload[5]=1; payload[9]=1; payload[17]=1; payload[269]=25
 return {commandCategory=122,time=10,player=1,size=272,data=require('code/utils').tableToHex(payload)}
end
manifest={player=1,variant='SHC',automarket=adapter.current()}
''')

    def test_known_commit_requires_matching_registration_and_versions(self):
        self.check('''
assert(pcall(validation.sessionCommand,marketCommand(),manifest))
assert(adapter.compatible(manifest.automarket))
modules.protocol.getProtocolNumber=function() return 132 end
assert(not adapter.compatible(manifest.automarket))
allActiveExtensions[1].version='1.0.0'
assert(not pcall(adapter.current))
allActiveExtensions={}; assert(not adapter.compatible(manifest.automarket))
assert(adapter.compatible(nil))
''')

    def test_unknown_custom_protocol_invalid_actor_fee_flags_and_sizes_fail(self):
        self.check('''
for _,change in ipairs({{1,132},{5,2},{269,101},{272,255},{9,2},{17,2},{66,2}}) do
 local c=marketCommand(); local payload=require('code/utils').hexToTable(c.data)
 payload[change[1]]=change[2]; c.data=require('code/utils').tableToHex(payload)
 assert(not pcall(validation.sessionCommand,c,manifest))
end
local c=marketCommand(); c.commandCategory=121
assert(not pcall(validation.sessionCommand,c,manifest))
c=marketCommand(); c.size=271; c.data=c.data:sub(1,-3)
assert(not pcall(validation.sessionCommand,c,manifest))
assert(not pcall(validation.sessionCommand,marketCommand(),{player=1,variant='SHC'}))
''')
