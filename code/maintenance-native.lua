-- Observe the native phase, not elapsed real time or an expected path value.
-- Repeated maintenance-only passes cost one native increment each. Only the
-- rare unclocked world admission crosses into Lua to preserve execution order.
local fixes=require('code/fixes')
local native=require('code/native')
local M={}
local profiles={
  SHC={
    maintenance={address=0x45ce7c,bytes={185,8,50,169,1}},
    world={address=0x45cf56,bytes={139,206,232,147,145,255,255},target=0x4560f0},
    gameState=0x112b0b8,
  },
  Extreme={
    maintenance={address=0x45d08c,bytes={185,8,103,82,2}},
    world={address=0x45d166,bytes={139,206,232,179,145,255,255},target=0x456320},
    gameState=0x112b538,
  },
}
M.profiles=profiles

function M.verify()
  local profile=assert(profiles[native.profile.name])
  for _,key in ipairs({'maintenance','world'}) do
    require('code/hook-check').verify(profile[key],'Recorder maintenance hook conflicts at '..key)
  end
  return profile
end

-- cdecl(count, logicalPause): use the real coordinator and its existing
-- subsystem hooks. A positive pause requests maintenance only; -1 admits the
-- native unclocked world step. Restore the viewer's logical pause afterwards.
function M.runner(sites,profile,state,origin)
  local bytes={}
  local function emit(...) for _,b in ipairs({...}) do bytes[#bytes+1]=b end end
  local function word(value)
    value=value%4294967296
    for _=1,4 do emit(value%256); value=math.floor(value/256) end
  end
  emit(0x53,0x56,0x57,0x8b,0x5c,0x24,0x10,0x8b,0x7c,0x24,0x14)
  emit(0x8b,0x35); word(sites.paused)
  emit(0xc7,0x05); word(state+20); word(1)
  local again=#bytes
  emit(0x89,0x3d); word(sites.paused)
  emit(0xb9); word(profile.gameState)
  emit(0xe8); word(sites.tickEntry.address-origin-#bytes-4)
  emit(0x4b,0x0f,0x85); word(again-#bytes-4)
  emit(0x89,0x35); word(sites.paused)
  emit(0xc7,0x05); word(state+20); word(0)
  emit(0x5f,0x5e,0x5b,0xc3)
  return bytes
end

function M.new(engine,profile,onWorld)
  local self=setmetatable({engine=engine,state=core.allocate(24,true)},{__index=M})
  self.internalWork=self.state+20
  local callback=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xc3})
  core.detourCode(function(registers) onWorld(); return registers end,callback,5)
  local function site(key,patch,kind)
    local source=profile[key]
    return {address=source.address,bytes=source.bytes,target=source.target,kind=kind,
      patch=patch,state=self.state,clock=engine.commands.tick,callback=callback}
  end
  fixes.install({site('maintenance','maintenanceCount','raw'),site('world','unclockedWorld','prefixCall')},
    self.state,engine.base+0x618)
  local runner=core.allocateCode(#M.runner(engine.sites,profile,self.state,0))
  core.writeCode(runner,M.runner(engine.sites,profile,self.state,runner))
  self.runNative=core.exposeCode(runner,2,0)
  return self
end

function M:start()
  self:stop()
  core.writeInteger(self.state+4,self.engine:tick())
  core.writeInteger(self.state+8,0)
  core.writeInteger(self.state+12,0)
  core.writeInteger(self.state+16,0)
  core.writeInteger(self.state,1)
end
function M:stop() core.writeInteger(self.state,0) end
function M:take()
  assert(core.readInteger(self.state+12)==0,'Recorder maintenance counter overflow')
  local count=core.readInteger(self.state+8)
  require('code/validation').integer(count,0,2147483647,'maintenance pass count')
  if count~=0 then core.writeInteger(self.state+8,0) end
  return count
end
function M:replay(kind,count)
  require('code/validation').integer(kind,1,2,'unclocked work kind')
  require('code/validation').integer(count,1,2147483647,'unclocked work count')
  assert(core.readInteger(self.state)==0 and core.readInteger(self.internalWork)==0,
    'Nested replay maintenance')
  local tick=self.engine:tick()
  self.runNative(count,kind==1 and 1 or -1)
  assert(self.engine:tick()==tick,'Recorded unclocked work advanced the match clock')
end
return M
