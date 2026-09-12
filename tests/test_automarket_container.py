"""The map-extensions ZIP contract and cleanup, without touching live state."""
import unittest
import test_recorder as fixture


class AutomarketContainerTests(unittest.TestCase):
    setUp=fixture.RecorderTests.setUp
    check=fixture.RecorderTests.check

    def prepare(self):
        self.check('''
allActiveExtensions={{name='automarket',version='1.1.0'},
 {name='protocol',version='1.0.0'},{name='map-extensions',version='1.0.0'}}
modules={protocol={getProtocolNumber=function() return 130 end},['map-extensions']=mapSaveOwner}
closed=0; calls={}; data='\\2\\0\\0\\0'..string.rep('x',2412)
core.openLibraryHandle=function(path)
 assert(path=='ucp/modules/map-extensions/luamemzip.dll')
 return {require=function(_,name)
  assert(name=='luamemzip')
  return {MemoryZip=function(_,input,compression,mode)
   assert(input==nil and compression==nil and mode=='w')
   return {
    open_entry=function(_,name) calls[#calls+1]=name; return true end,
    write_entry=function(_,contents) assert(contents==data); return not failWrite end,
    close_entry=function() return true end,
    serialize=function() return 'zip bytes',9 end,
    close=function() closed=closed+1 end,
   }
  end}
 end}
end
marketContainer=require('code/automarket-container')
descriptor={version='1.1.0',protocol=130}
''')

    def test_existing_zip_api_uses_exact_module_entry_without_serializers(self):
        self.prepare()
        self.check('''
assert(marketContainer.encode(data,descriptor)=='zip bytes')
assert(closed==1 and #calls==1 and calls[1]=='automarket/automarketplayerdata.bin')
''')

    def test_zip_failure_closes_handle(self):
        self.prepare()
        self.check('''
failWrite=true
assert(not pcall(marketContainer.encode,data,descriptor) and closed==1)
''')

    def test_invalid_snapshot_or_other_protocol_never_opens_zip(self):
        self.prepare()
        self.check('''
assert(not pcall(marketContainer.encode,'short',descriptor))
descriptor.protocol=131
assert(not pcall(marketContainer.encode,data,descriptor))
assert(#calls==0 and closed==0)
''')
