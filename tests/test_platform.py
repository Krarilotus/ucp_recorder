"""Exercise framework-owned Windows resolution and reusable C-string buffers."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class PlatformTests(unittest.TestCase):
    def test_removal_checks_paths_and_links_and_never_overwrites(self):
        lua=self.runtime()
        lua.execute('''
core.readString=function(a,n) return stringRead(a):sub(1,n) end
local moves=0
platform.stdcall=function(_,name)
 if name=='GetFileAttributesA' then return function(a)
  local p=stringRead(a)
  return linked==p and 1040 or 16
 end end
 if name=='CreateDirectoryA' then return function() return 1 end end
 if name=='GetFullPathNameA' then return function(a,n,out)
  local p='C:\\\\Game\\\\'..stringRead(a):gsub('/','\\\\')
  if escapePath then p='C:\\\\elsewhere' end
  core.writeString(out,p..'\\0'); return #p
 end end
 if name=='MoveFileExA' then return function(a,b,flags)
  moves=moves+1; assert(flags==8)
  assert(stringRead(a)=='C:\\\\Game\\\\ucp\\\\replays\\\\test')
  assert(stringRead(b)=='C:\\\\Game\\\\ucp\\\\replays\\\\removed\\\\test')
  return exists and 0 or 1
 end end
 error(name)
end
for _,id in ipairs({'../other','a/b','',string.rep('x',80)}) do
 assert(not pcall(platform.removeReplay,'ucp/replays',id))
end
for _,p in ipairs({'ucp/replays','ucp/replays/test','ucp/replays/removed'}) do
 linked=p; assert(not pcall(platform.removeReplay,'ucp/replays','test'))
end
linked=nil; escapePath=true; assert(not pcall(platform.removeReplay,'ucp/replays','test'))
assert(moves==0)
escapePath=false; platform.removeReplay('ucp/replays','test'); assert(moves==1)
exists=true; assert(not pcall(platform.removeReplay,'ucp/replays','test'))
''')

    def runtime(self):
        lua=LuaRuntime()
        lua.globals().source_root=ROOT.as_posix()
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
memory={}; nextAddress=0x70000000; targets={}; calls={}; resolutions=0
local function stringWrite(a,s) for i=1,#s do memory[a+i-1]=s:byte(i) end end
function stringRead(a)
 local s={}; for i=0,4095 do local b=memory[a+i] or 0; if b==0 then return table.concat(s) end; s[#s+1]=string.char(b) end
 error('Unterminated string')
end
core={
 allocate=function(n) local a=nextAddress; nextAddress=a+n; return a end,
 writeString=stringWrite,
 callTo=function(a) return {target=a} end,
 calculateCodeSize=function(code) return #code+4 end,
 allocateCode=function(n) return core.allocate(n) end,
 writeCode=function(a,code) for _,v in ipairs(code) do if type(v)=='table' then targets[a]=v.target end end end,
 exposeCode=function(a) return assert(calls[targets[a]],'Unexpected native target') end,
}
local exports={MoveFileExA=0x30001000,GetFileAttributesA=0x30002000,CreateDirectoryA=0x30003000,
 GetTickCount=0x30004000,timeGetTime=0x30005000}
ucp={internal={getLibraryProcAddressA=function(library,name)
 resolutions=resolutions+1
 assert(library==(name=='timeGetTime' and 'winmm.dll' or 'kernel32.dll'))
 return assert(exports[name],'Windows export not found: '..name)
end}}
calls[0x30001000]=function(a,b,flags) source=stringRead(a); destination=stringRead(b); assert(flags==9); return 1 end
calls[0x30002000]=function(a) inspected=stringRead(a); return attributes or 16 end
calls[0x30003000]=function(a,b) created=stringRead(a); assert(b==0); return 0 end
calls[0x30004000]=function() return -1 end
calls[0x30005000]=function() return -2 end
platform=require('code/platform')
''')
        return lua

    def test_framework_resolution_and_shorter_reused_paths(self):
        self.runtime().execute('''
platform.replace('long-source.tmp','long-destination.json')
platform.replace('a','b'); assert(source=='a' and destination=='b')
assert(not platform.mkdir('long-folder-name'))
assert(not platform.mkdir('x')); assert(created=='x' and inspected=='x')
assert(resolutions==3)
attributes=0; assert(not pcall(platform.mkdir,'plain-file'))
assert(not pcall(platform.mkdir,'bad\\0path'))
''')

    def test_clocks_and_function_cache_preserve_unsigned_time_and_abi(self):
        self.runtime().execute('''
assert(platform.milliseconds()==4294967295)
assert(platform.multimediaMilliseconds()==4294967294)
assert(platform.milliseconds()==4294967295 and platform.multimediaMilliseconds()==4294967294)
assert(resolutions==2)
assert(platform.stdcall('kernel32.dll','GetTickCount',0)==platform.stdcall('kernel32.dll','GetTickCount',0))
assert(not pcall(platform.stdcall,'kernel32.dll','GetTickCount',1))
assert(resolutions==2)
''')

    def test_owner_failure_and_invalid_inputs_do_not_create_a_bridge(self):
        self.runtime().execute('''
local initial=nextAddress
local ok,reason=pcall(platform.stdcall,'kernel32.dll','MissingSymbol',0)
assert(not ok and reason:find('Windows export not found',1,true))
assert(nextAddress==initial)
for _,count in ipairs({-1,11,1.5}) do assert(not pcall(platform.stdcall,'kernel32.dll','GetTickCount',count)) end
assert(not pcall(platform.stdcall,'unexpected.dll','GetTickCount',0))
ucp.internal.getLibraryProcAddressA=function() return 0 end
assert(not pcall(platform.stdcall,'kernel32.dll','GetTickCount',0))
assert(nextAddress==initial)
''')
