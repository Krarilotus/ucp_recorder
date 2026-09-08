local native=require('code/native')
local Engine=require('code/engine')
local Session=require('code/session-recorder')
local module={}

local function enable(self,config,stage,install)
  local multiplayerCapture=config.autoRecord~=false
  local multiplayerObserve=multiplayerCapture or config.multiplayerDiagnostics
  local seed
  stage('seed options',function()
    if config.useFixedSeed then
      seed=require('code/validation').integer(config.fixedSeed,-2147483648,2147483647,'fixed seed')
    end
  end)
  stage('native executable checks',native.verify)
  stage('Automarket compatibility',require('code/automarket-replay').current)
  local sites=stage('session hook checks',Engine.verify)
  local uiSites=stage('menu hook checks',require('code/native-ui').verify)
  local fixes=require('code/fixes')
  local fixSites=stage('simulation hook checks',function() return fixes.verify(seed) end)
  if multiplayerObserve then
    stage('network diagnostic checks',require('code/network-observer').verify)
    stage('world-hash diagnostic checks',require('code/world-hash-observer').verify)
  end
  if config.multiplayerDiagnostics or config.singleplayerRngDiagnostics then
    stage('RNG diagnostic checks',require('code/rng-observer').verify)
  end
  stage('recorded settings',require('code/sessions').captureSettings)
  install(function()
    local engine=Engine.new(sites)
    if multiplayerCapture then engine.trace=require('code/multiplayer-capture').new(engine,config)
    elseif config.multiplayerDiagnostics then engine.trace=require('code/multiplayer-trace').new(engine,config) end
    local simulation,controls={},{}
    for _,site in ipairs(fixSites) do
      local group=(site.name=='pause' or site.name=='pausedCamera') and controls or simulation
      group[#group+1]=site
    end
    local rngReturnAddresses=fixes.install(simulation,engine.scope,engine.base+0x618,seed)
    fixes.install(controls,engine.scope,engine.base+0x618,nil,engine.offlineFlag)
    if engine.trace then engine.trace.rngReturnAddresses=rngReturnAddresses end
    local recorder=Session:new(engine,config)
    if multiplayerCapture then engine.trace.enabled=function() return recorder.autoRecord end end
    fixes.install({sites.resultsTimer},recorder.resultsHold,engine.base+0x618,nil,engine.offlineFlag)
    if recorder.rngTrace then recorder.rngTrace.returnAddresses=rngReturnAddresses end
    self.recorder=recorder
    local loadLifecycle=require('code/load-lifecycle').new(recorder)
    engine:install(recorder)
    if engine.trace then
      require('code/network-observer').install(engine.trace)
      require('code/world-hash-observer').install(engine.trace)
    end
    if config.multiplayerDiagnostics or recorder.rngTrace then
      -- One native hook per stream even when both diagnostic options are on.
      require('code/rng-observer').install({engine=engine,observe=function(_,event,...)
        if engine.trace then engine.trace:observe(event,...) end
        if recorder.rngTrace then recorder.rngTrace:observe(event,...) end
      end})
    end
    local ui=require('code/ui')
    ui.createButtons(recorder,uiSites)

    local function observe(address,size,callback)
      core.detourCode(function(registers)
        recorder:guard(function()
          recorder:reconcileMode()
          callback(registers)
        end)
        return registers
      end,address,size)
    end
    observe(native.addr(0x442877),5,function() loadLifecycle:cancel(); recorder:beginMatch() end)
    observe(native.addr(0x4428c6),10,function()
      if engine.trace then engine.trace:observe('stop','new match') end
      recorder:prepareRecording()
      ui.resetButtons()
    end)
    observe(native.addr(0x46b358),6,function(registers)
      recorder:onMenuView(registers.EBP)
    end)
    observe(native.addr(0x495337),6,function()
      loadLifecycle:begin()
    end)
    observe(sites.loadWorldComplete.address,6,function(registers) loadLifecycle:readComplete(registers.ESI) end)
    observe(sites.loadHandlerComplete.address,5,function() loadLifecycle:finish() end)
    observe(native.addr(0x494ba5),5,function() recorder:reset() end)

    local tickCallback=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xC3})
    observe(tickCallback,5,function() recorder:onTick() end)
    local multiplayerTick
    if engine.trace then
      multiplayerTick=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xC3})
      core.detourCode(function(registers)
        engine.trace:observe('onTick')
        return registers
      end,multiplayerTick,5)
    end
    -- A stopped replay must also reject paused/loading callers that never reach
    -- the clock hook. The callback can stop the current call at its epilogue;
    -- subsequent calls return at entry, before map/path maintenance.
    fixes.install({fixes.tickEntry(sites,recorder.halt,recorder.playbackActive)},
      engine.scope,engine.base+0x618,nil,engine.offlineFlag)
    fixes.installTick(sites.tick,engine.scope,engine.base+0x618,recorder.halt,tickCallback,multiplayerTick,
      engine.offlineFlag,sites.tickExit.address)
    core.detourCode(function(registers)
      if recorder.rngTrace then recorder.rngTrace:observe('afterTick') end
      if engine.trace then engine.trace:observe('afterTick') end
      if recorder.active and recorder.mode=='play' and recorder.afterTick then
        recorder:guard(function() recorder:afterTick() end)
      end
      return registers
    end,sites.tickReturned.address,#sites.tickReturned.bytes)
  end)
end

function module:enable(config)
  self.startup=require('code/startup').run(function(stage,install) enable(self,config,stage,install) end)
  return self.startup
end

function module:disable()
  if self.recorder then self.recorder:reset() end
end
return module
