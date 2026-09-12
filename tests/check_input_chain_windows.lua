-- Console-only x86 check with installed Lua/RPS and WinProc Handler DLLs.
-- lua_rps_host.exe <this script> <recorder source> <framework code> <winProcHandler.dll>
-- tests/lua_rps_host.cpp initializes the RPS callback state as UCP does.
local source,framework,library=assert(arg[1]),assert(arg[2]),assert(arg[3])
package.path=source..'/?.lua;'..package.path
ucp={internal=require('RPS')}
core=dofile(framework..'/core.lua');package.loaded.core=core
utils=dofile(framework..'/utils.lua')
local exports=assert(package.loadlib(library,'luaopen_winProcHandler'))()
modules={winProcHandler={cinterface=function()
 return {RegisterProc=exports.funcAddress_RegisterProc,CallNextProc=exports.funcAddress_CallNextProc}
end}}
local chain=require('code/input-chain')
local platform=require('code/platform')
local nativeCalls,before,after,handled,errors=0,0,0,0,0
local nativeStub=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xC2,0x10,0})
local nativeOriginal=core.hookCode(function(_,window,message,key,data)
 assert(window==123 and message==0x100 and key==65 and data==987)
 nativeCalls=nativeCalls+1;return 42
end,nativeStub,5,1,5)
core.writeInteger(exports.address_FillWithWindowProcCallback,nativeStub)
local first=chain.install(chain.interface(),function() before=before+1;return false end,error)
local consume,fail=false,false
local recorder=chain.install(chain.interface(),function()
 handled=handled+1;if fail then error('injected handler failure') end
 return consume,17
end,function() errors=errors+1 end)
local last=chain.install(chain.interface(),function() after=after+1;return false end,error)
assert(first.priority==100000 and recorder.priority==100001 and last.priority==100002)
local main=platform.stdcallAddress(exports.funcAddress_GetMainProc,0)()
local dispatch=platform.stdcallAddress(main,4)
assert(dispatch(123,0x100,65,987)==42)
assert(before==1 and handled==1 and after==1 and nativeCalls==1)
consume=true;assert(dispatch(123,0x100,65,987)==17)
assert(before==2 and handled==2 and after==1 and nativeCalls==1)
assert(recorder.nextProc(recorder.priority,123,0x100,65,987)==42)
assert(before==2 and handled==2 and after==2 and nativeCalls==2)
consume=false;fail=true;assert(dispatch(123,0x100,65,987)==0 and errors==1)
assert(nativeCalls==2 and after==2)
fail=false
for _=1,1000 do assert(dispatch(123,0x100,65,987)==42) end
assert(nativeCalls==1002 and before==1003 and handled==1003 and after==1002)
assert(nativeOriginal and first.original and recorder.original and last.original)
print('PASS: native WinProc chain, priority collisions, consumption, tail dispatch, errors and 1000 repetitions')
