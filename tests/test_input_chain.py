"""Recorder uses the owner priority and never patches the game WndProc."""
from pathlib import Path
import unittest
from lupa.luajit21 import LuaRuntime

ROOT=Path(__file__).resolve().parents[1]


class InputChainTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime()
        self.lua.globals().source_root=ROOT.as_posix()
        self.lua.execute('''
package.path=source_root..'/?.lua;'..package.path
local interface={RegisterProc=101,CallNextProc=102}
modules={winProcHandler={cinterface=function() return interface end}}
forwarded,errors=0,0
package.loaded['code/platform']={stdcallAddress=function(address,count)
 if address==101 then
  assert(count==2);return function(callback,priority)
   assert(callback==1000 and priority==100000);return failed and -2147483648 or 100007
  end
 end
 assert(address==102 and count==5)
 return function(priority,window,message,key,data)
  assert(priority==100007 and window==20 and message==30 and key==40 and data==50)
  forwarded=forwarded+1;if downstreamFailure then error('downstream failure') end
  return 42
 end
end}
core={allocateCode=function(bytes)
 assert(#bytes==8 and bytes[6]==0xC2 and bytes[7]==20);return 1000
end,hookCode=function(callback,address,count,convention,size)
 assert(address==1000 and count==6 and convention==1 and size==5)
 hook=callback;return function() end
end}
chain=require('code/input-chain')
function install()
 return chain.install(chain.interface(),function(window,message,key,data)
  assert(window==20 and message==30 and key==40 and data==50)
  if handlerFailure then error('handler failure') end
  return consumed,17
 end,function() errors=errors+1;error('error reporter failed') end)
end
''')

    def test_assigned_priority_return_value_and_consumption(self):
        self.lua.execute('''
local installed=install();assert(installed.priority==100007)
assert(hook(999,100007,20,30,40,50)==42 and forwarded==1)
consumed=true;assert(hook(999,100007,20,30,40,50)==17 and forwarded==1)
''')

    def test_errors_cannot_escape_or_repeat_downstream(self):
        self.lua.execute('''
install();handlerFailure=true
assert(hook(0,100007,20,30,40,50)==0 and forwarded==0 and errors==1)
handlerFailure=false;downstreamFailure=true
assert(hook(0,100007,20,30,40,50)==0 and forwarded==1 and errors==2)
''')

    def test_missing_export_and_failed_registration(self):
        self.lua.execute('''
failed=true;assert(not pcall(install))
modules.winProcHandler.cinterface=function() return {RegisterProc=0,CallNextProc=102} end
assert(not pcall(chain.interface))
modules=nil;assert(not pcall(chain.interface))
''')
