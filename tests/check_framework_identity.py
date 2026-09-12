"""Real framework version parser/environment with fixture process/hash boundaries."""
import hashlib
from pathlib import Path
from check_load_bindings import LoadFixture


def check(path,variant,framework,protocol,ui):
    f=LoadFixture(path,variant,protocol,ui,framework);lua=f.lua();g=lua.globals()
    g.root=f.root.as_posix();g.framework=framework.as_posix()
    g.read_string=lambda a:f.read(a,len(f.image)-(a-f.base)).split(b'\0',1)[0].decode('ascii')
    g.read_byte=lambda a:f.read(a,1)[0]
    g.exe=path.as_posix();digest=hashlib.sha256(f.raw).hexdigest();g.digest=digest
    lua.execute('''
core.readString=read_string;core.readByte=read_byte
core.allocate=function() return 0x30000000 end;core.writeBytes=function() end
package.loaded.extensions={};package.loaded.version={}
local originalOpen=io.open
io.open=function(path,...)
 if path=='ucp/ucp-version.yml' then return {read=function() return '' end,close=function() end} end
 return originalOpen(path,...)
end
yaml={eval=function() return {major=3,minor=0,patch=7,sha='fixture'} end}
local owner=dofile(framework..'/data/version.lua');owner.initialize()
data={version=owner}
-- Match main.lua's module environment. Restricted require loads the production
-- native module and validation from this checkout without host-module imports.
LOG_LEVELS={INFO=1};ucp={internal={log=function() end}}
local environment=dofile(framework..'/extensions/environment.lua')
local env=environment.createRestrictedEnvironment('recorder',root,true,_G,true)
local loadModule=env.require
local calls=0
rawset(env,'require',function(name)
 if name=='code/platform' then return {identity=function() return {executable=exe} end} end
 if name=='code/native-hash' then return {file=function(path,limit)
   assert(path==exe and limit==64*1024*1024);calls=calls+1;return digest end} end
 return loadModule(name)
end)
identity=loadModule('code/native').verify()
assert(identity.sha256==digest and calls==1)
assert(identity.header==nil and identity.addresses==nil)
''')
    assert g.identity.name==variant
    return dict(variant=variant,sha256=digest,frameworkVersion=dict(g.data.version.game_version.items()),
                actualRestrictedEnvironment=True,hashBoundary='Python fixture',liveGame=False)
