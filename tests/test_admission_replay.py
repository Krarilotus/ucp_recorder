import unittest
import test_recorder as fixture


class AdmissionReplayTests(unittest.TestCase):
    check=fixture.RecorderTests.check
    setUp=fixture.RecorderTests.setUp

    def test_only_the_recorded_lobby_protocol_is_safe_to_omit(self):
        self.check('''
local adapter=require('code/admission-replay')
local descriptor={version=1,protocol=132}
local bytes={};for i=1,80 do bytes[i]=0 end
bytes[1]=132;bytes[5]=1;bytes[9]=7;bytes[13]=2
local packet={category=121,scheduledTime=0,size=80,data=require('code/utils').tableToHex(bytes)}
assert(adapter.packet(packet,descriptor))
assert(not adapter.packet(packet,nil))
for _,change in ipairs({{1,133},{5,2},{9,0},{13,0},{13,9}}) do
 local old=bytes[change[1]];bytes[change[1]]=change[2]
 packet.data=require('code/utils').tableToHex(bytes)
 assert(not adapter.packet(packet,descriptor));bytes[change[1]]=old
end
packet.data=require('code/utils').tableToHex(bytes)
packet.category=122;assert(not adapter.packet(packet,descriptor))
packet.category=121;packet.scheduledTime=64;assert(not adapter.packet(packet,descriptor))
packet.scheduledTime=0;packet.size=79;assert(not adapter.packet(packet,descriptor))
''')

    def test_descriptor_requires_the_real_protocol_registration(self):
        self.check('''
local adapter=require('code/admission-replay')
allActiveExtensions={{name='protocol',version='1.0.0'}}
assert(adapter.current()==nil)
allActiveExtensions[1].version='1.1.0'
modules={protocol={multiplayerAdmissionVersion=function()return 1 end,
 getProtocolNumber=function(_,extension,name)
  assert(extension=='protocol' and name=='content-admission-v1');return 132
 end}}
assert(adapter.current().protocol==132)
modules.protocol.getProtocolNumber=function()return nil end;assert(adapter.current()==nil)
modules.protocol.multiplayerAdmissionVersion=function()return 2 end
assert(not pcall(adapter.current))
''')
