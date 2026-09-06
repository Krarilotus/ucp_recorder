"""Exercise system-export bootstrap and C-string reuse without loading DLLs."""
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

    def runtime(self, variant='SHC', forward=False):
        lua=LuaRuntime()
        lua.globals().source_root=ROOT.as_posix()
        lua.globals().variant=variant
        lua.globals().forward=forward
        lua.execute('''
package.path=source_root..'/?.lua;'..package.path
package.loaded['code/native']={profile={name=variant}}
memory={}; nextAddress=0x70000000; targets={}; calls={}
local function write(a,v,n)
 for i=0,n-1 do memory[a+i]=v%256; v=math.floor(v/256) end
end
local function read(a,n)
 local v=0; for i=n-1,0,-1 do v=v*256+(memory[a+i] or 0) end; return v
end
local function stringWrite(a,s) for i=1,#s do memory[a+i-1]=s:byte(i) end end
function stringRead(a)
 local s={}; for i=0,4095 do local b=memory[a+i] or 0; if b==0 then return table.concat(s) end; s[#s+1]=string.char(b) end
 error('Unterminated string')
end
core={
 allocate=function(n) local a=nextAddress; nextAddress=a+n; return a end,
 writeString=stringWrite, readByte=function(a) return read(a,1) end,
 readInteger=function(a) return read(a,4) end, readSmallInteger=function(a) return read(a,2) end,
 callTo=function(a) return {target=a} end,
 calculateCodeSize=function(code) return #code+4 end,
 allocateCode=function(n) return core.allocate(n) end,
 writeCode=function(a,code) for _,v in ipairs(code) do if type(v)=='table' then targets[a]=v.target end end end,
 exposeCode=function(a) return assert(calls[targets[a]],'Unexpected native target') end,
}
function export(base,symbol,target)
 write(base,0x5a4d,2); write(base+0x3c,0x80,4); write(base+0x80,0x4550,4)
 write(base+0x80+24,0x10b,2); write(base+0x80+120,0x200,4); write(base+0x80+124,0x100,4)
 write(base+0x200+20,1,4); write(base+0x200+24,1,4)
 write(base+0x200+28,0x310,4); write(base+0x200+32,0x320,4); write(base+0x200+36,0x330,4)
 write(base+0x320,0x400,4); write(base+0x330,0,2); stringWrite(base+0x400,symbol..'\\0')
 if type(target)=='string' then write(base+0x310,0x280,4); stringWrite(base+0x280,target..'\\0')
 else write(base+0x310,target-base,4) end
end
export(0x10000000,'GetProcAddress',forward and 'KERNELBASE.GetProcAddress' or 0x10001000)
export(0x20000000,'GetProcAddress',0x20001000)
write(variant=='SHC' and 0x59e128 or 0x59e12c,0x12340000,4)
calls[0x12340000]=function(a)
 local name=stringRead(a)
 if name:lower()=='kernel32.dll' then return 0x10000000 end
 assert(name=='KERNELBASE.dll',name); return 0x20000000
end
calls[0x10001000]=function(handle,name)
 assert(handle==0x10000000)
 local symbol=stringRead(name); assert(symbol=='MoveFileExA' or symbol=='GetFileAttributesA' or symbol=='CreateDirectoryA',symbol)
 return ({MoveFileExA=0x30001000,GetFileAttributesA=0x30002000,CreateDirectoryA=0x30003000})[symbol]
end
calls[0x20001000]=calls[0x10001000]
calls[0x30001000]=function(a,b,flags) source=stringRead(a); destination=stringRead(b); assert(flags==9); return 1 end
calls[0x30002000]=function(a) inspected=stringRead(a); return attributes or 16 end
calls[0x30003000]=function(a,b) created=stringRead(a); assert(b==0); return 0 end
platform=require('code/platform')
''')
        return lua

    def test_import_profiles_forwarders_and_shorter_reused_paths(self):
        for variant in ('SHC','Extreme'):
            for forward in (False,True):
                with self.subTest(variant=variant,forward=forward):
                    lua=self.runtime(variant,forward)
                    lua.execute('''
platform.replace('long-source.tmp','long-destination.json')
platform.replace('a','b'); assert(source=='a' and destination=='b')
assert(not platform.mkdir('long-folder-name'))
assert(not platform.mkdir('x')); assert(created=='x' and inspected=='x')
attributes=0; assert(not pcall(platform.mkdir,'plain-file'))
assert(not pcall(platform.mkdir,'bad\\0path'))
''')

    def test_missing_and_cyclic_exports_fail_explicitly(self):
        for target in ('KERNEL32.GetProcAddress','KERNELBASE.MissingSymbol','KERNELBASE.#1'):
            with self.subTest(target=target):
                lua=self.runtime()
                lua.globals().bad_target=target
                lua.execute('''
export(0x10000000,'GetProcAddress',bad_target)
local ok,reason=pcall(platform.replace,'a','b')
assert(not ok and tostring(reason):find('Windows export'))
''')
