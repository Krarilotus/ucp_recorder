"""UCP 3.0.7 VFS contracts: unpacked trees, ZIP listings and non-path options."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime


class ReplayAssetsTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().source_root=Path(__file__).resolve().parents[1].as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
local module='ucp/modules/packed-1.0.0'
local plugin='ucp/plugins/unpacked-1.0.0'
contents={[module..'.zip']=string.rep('a',64),[plugin..'/definition.yml']=string.rep('b',64),
 [plugin..'/data.zip']=string.rep('c',64),[plugin..'/code/init.lua']=string.rep('d',64),
 ['maps/test.map']=string.rep('e',64)}
listing={[module..'/']={},[plugin..'/']={plugin..'/definition.yml',plugin..'/data.zip'},
 [plugin..'/code/']={plugin..'/code/init.lua'}}
children={[module..'/']={},[plugin..'/']={plugin..'/code/',plugin..'/data/'},[plugin..'/code/']={}}
ucp={internal={io={files=function(path) return assert(listing[path],'Invalid path: '..path) end,
 directories=function(path) return assert(children[path],'Invalid directory: '..path) end}}}
io.open=function(path)
 if path:find('://',1,true) then error('Invalid path') end
 if contents[path] then return {close=function() return true end} end
end
package.loaded['code/native-hash']={prepare=function() end,file=function(path)
 return assert(contents[path],'Missing asset: '..path)
end}
assets=require('code/replay-assets')
extensions={{name='packed',version='1.0.0',type=function() return 'ModuleLoader' end},
 {name='unpacked',version='1.0.0',type=function() return 'PluginLoader' end}}
snapshot=assets.capture(extensions,{map='maps/test.map',text='https://example.invalid/page'})
''')

    def test_zip_and_folder_contents_are_identified_without_traversing_nested_archives(self):
        self.lua.execute('''
local count=0; for _ in pairs(snapshot.files) do count=count+1 end
assert(count==5 and snapshot.files['ucp/modules/packed-1.0.0.zip'])
assets.verify(snapshot)
''')

    def test_edited_and_missing_assets_fail_with_a_specific_path(self):
        self.lua.execute('''
local path='ucp/plugins/unpacked-1.0.0/code/init.lua'
contents[path]=string.rep('f',64)
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find(path,1,true))
contents[path]=nil
assert(not pcall(assets.verify,snapshot))
''')

    def test_a_folder_shadowing_the_recorded_zip_cannot_pass(self):
        self.lua.execute('''
listing['ucp/modules/packed-1.0.0/']={'ucp/modules/packed-1.0.0/definition.yml'}
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find('layout changed',1,true))
''')
