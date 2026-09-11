-- Offline benchmark with the shipped 32-bit Lua/RPS. No game attachment.
-- Usage: lua.exe benchmark_recording_boundary.lua <framework-code-dir> <recorder-dir>
local rps=require('RPS')
ucp={internal=rps}
local framework=assert(arg[1]); local root=assert(arg[2])
core=dofile(framework..'/core.lua'); package.loaded.core=core
utils=dofile(framework..'/utils.lua')
package.path=root..'/?.lua;'..package.path
local json=dofile(framework..'/vendor/json/json.lua')
local platform=require('code/platform')
local function stdcall(name,count)
  return platform.stdcallAddress(rps.getLibraryProcAddressA('kernel32.dll',name),count)
end
local counter,frequency=stdcall('QueryPerformanceCounter',1),stdcall('QueryPerformanceFrequency',1)
local timer=core.allocate(16,true)
local function integer64(p) return core.readInteger(p)%4294967296+core.readInteger(p+4)%4294967296*4294967296 end
assert(frequency(timer+8)~=0); local hz=integer64(timer+8)
local function clock() assert(counter(timer)~=0); return integer64(timer)*1000/hz end
local engine=setmetatable({rng=core.allocate(40017,true),
  sites={playerResources=core.allocate(9*0x39f4,true)}},{__index=require('code/engine')})
core.writeString(engine.rng,string.rep('x',40016))
for player=1,8 do core.writeString(engine.sites.playerResources+player*0x39f4,string.rep(string.char(64+player),100)) end
local boundary=engine:newRecordingBoundary()
local iterations=20000
local samples={}
local function measure(name,action)
  collectgarbage('collect')
  local began=clock()
  for i=1,iterations do
    -- Both paths see changing state, rather than one interned constant string.
    core.writeInteger(engine.rng+4,i)
    action()
  end
  local ms=clock()-began
  samples[#samples+1]={name=name,milliseconds=ms,microsecondsPerTick=ms*1000/iterations}
end
local old={}
for pass=1,5 do
  measure('old Lua retention',function()
    old.state=engine:rngState(); old.resources=engine:resourceData(); old.rng=engine:rngData()
  end)
  measure('native boundary retention',function() boundary:capture() end)
  local rng,resources=boundary:read()
  assert(rng==old.rng and resources==old.resources)
  local state=boundary:rngState(); for i=1,4 do assert(state[i]==old.state[i]) end
end
print(json:encode({runtime=_VERSION,iterations=iterations,samples=samples,
  scope='Isolated changing-state retention using real shipped Lua/RPS and emitted x86. Includes the same synthetic source mutation in both paths. Excludes game simulation, tick hooks, I/O and verification.'}))
