"""UCP 3.0.7 VFS contracts: unpacked trees, ZIP listings and non-path options."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime


class ReplayAssetsTests(unittest.TestCase):
    def test_directory_enumeration_yields_and_can_be_cancelled_before_hashing(self):
        self.lua.execute('''
local hashes=0
local digest=require('code/native-hash')
local original=digest.file
digest.file=function(...) hashes=hashes+1; return original(...) end
local root='maps/empty'
snapshot.roots[root]=true; listing[root..'/']={}; children[root..'/']={}
for i=1,200 do
 local path=root..'/'..i..'/'
 children[root..'/'][i]=path; listing[path]={}; children[path]={}
end
local now=0
local task=require('code/preparation-task').new(function(progress)
 assets.verify(snapshot,function(message) now=now+1; progress(message) end)
 return true
end,function() return now end)
task:step()
assert(task.status=='pending' and hashes==0)
task:cancel(); task:step()
assert(task.status=='cancelled' and hashes==0)
assets.verify(snapshot) -- cancellation changes neither inventory nor future verification
assert(hashes==5)
''')

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
ucp={internal={resolveAliasedPath=function(path) return path end,io={files=function(path) return assert(listing[path],'Invalid path: '..path) end,
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

    def test_added_files_and_nested_directories_cannot_silently_change_the_profile(self):
        self.lua.execute('''
local root='ucp/plugins/unpacked-1.0.0'
local path=root..'/code/new.lua'
listing[root..'/code/'][2]=path; contents[path]=string.rep('f',64)
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find('New asset',1,true) and reason:find(path,1,true))
listing[root..'/code/'][2]=nil
children[root..'/'][3]=root..'/new/'
listing[root..'/new/']={root..'/new/extra.lua'}; children[root..'/new/']={}
assert(not pcall(assets.verify,snapshot))
children[root..'/'][3]=nil
assets.verify(snapshot)
''')

    def test_configured_directory_membership_is_preserved_without_hashing_unrelated_files(self):
        self.lua.execute('''
listing['maps/custom/']={'maps/custom/a.map'}; children['maps/custom/']={}
contents['maps/custom/a.map']=string.rep('f',64)
snapshot=assets.capture(extensions,{directory='maps/custom/'})
assert(snapshot.roots['maps/custom'])
contents['unrelated.map']='not part of this configuration'
assets.verify(snapshot)
listing['maps/custom/'][2]='maps/custom/b.map'
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find('maps/custom/b.map',1,true))
''')

    def test_directory_listing_cannot_escape_its_recorded_root(self):
        self.lua.execute('''
listing['ucp/plugins/unpacked-1.0.0/code/'][1]='outside.lua'
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find('escaped its parent',1,true))
''')

    def test_physical_folder_beside_a_nested_archive_is_not_skipped(self):
        self.lua.execute('''
local path='ucp/plugins/unpacked-1.0.0/data/'
listing[path]={path..'new.lua'}; children[path]={}
contents[path..'new.lua']=string.rep('f',64)
local ok,reason=pcall(assets.verify,snapshot)
assert(not ok and reason:find(path..'new.lua',1,true))
snapshot=assets.capture(extensions,{})
assert(snapshot.files[path..'new.lua'])
assets.verify(snapshot)
''')

    def test_configured_ucp_aliases_use_resolved_parent_and_file_identity(self):
        self.lua.execute(r"""
local root='ucp/plugins/unpacked-1.0.0'
local aliases={['ucp/plugins/unpacked/']=root..'/', ['ucp/plugins/unpacked-*/']=root..'/'}
ucp.internal.resolveAliasedPath=function(path)
 for alias,target in pairs(aliases) do
  if path:sub(1,#alias)==alias then return target..path:sub(#alias+1) end
 end
 return path
end
-- UCP's file and directory APIs resolve aliases before returning versioned paths.
local files,dirs=ucp.internal.io.files,ucp.internal.io.directories
ucp.internal.io.files=function(path) return files(ucp.internal.resolveAliasedPath(path)) end
ucp.internal.io.directories=function(path) return dirs(ucp.internal.resolveAliasedPath(path)) end
for _,directory in ipairs({'ucp/plugins/unpacked/code/', 'ucp/plugins/unpacked-*/code/',
 'ucp/plugins/unpacked/', 'ucp/plugins/unpacked', 'ucp\\plugins\\unpacked\\code\\'}) do
 local captured=assets.capture(extensions,{directory=directory,file='ucp/plugins/unpacked-*/code/init.lua'})
 assert(captured.files[root..'/code/init.lua'])
 for path in pairs(captured.roots) do assert(not path:find('unpacked/',1,true) and not path:find('*',1,true)) end
 for path in pairs(captured.files) do assert(not path:find('unpacked/',1,true) and not path:find('*',1,true)) end
 assets.verify(captured)
end
-- Aliases do not grant permission to accept an unrelated listing result.
listing[root..'/code/'][1]='elsewhere/init.lua'
local ok,reason=pcall(assets.capture,extensions,{directory='ucp/plugins/unpacked/code/'})
assert(not ok and reason:find('escaped its parent',1,true) and reason:find('elsewhere/init.lua',1,true))
""")
