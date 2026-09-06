local native=require('code/native')
local Engine=require('code/engine')
local Session=require('code/session-recorder')
local module={}

local function enable(self,config,stage)
  stage('native executable checks',native.verify)
  stage('Automarket compatibility',require('code/automarket-replay').current)
  local sites=stage('session hook checks',Engine.verify)
  local uiSites=stage('menu hook checks',require('code/native-ui').verify)
  local fixes=require('code/fixes')
  local fixSites=stage('simulation hook checks',fixes.verify)
  if config.multiplayerDiagnostics then
    stage('network diagnostic checks',require('code/network-observer').verify)
    stage('RNG diagnostic checks',require('code/rng-observer').verify)
    stage('world-hash diagnostic checks',require('code/world-hash-observer').verify)
  end
  local seed
  stage('seed options',function()
    if config.useFixedSeed then
      seed=require('code/validation').integer(config.fixedSeed,-2147483648,2147483647,'fixed seed')
    end
  end)
  stage('recorded settings',require('code/sessions').captureSettings)
  stage('hook and menu installation',function()
    local engine=Engine.new(sites)
    if config.multiplayerDiagnostics then engine.trace=require('code/multiplayer-trace').new(engine,config) end
    local rngReturnAddresses=fixes.install(fixSites,engine.scope,engine.base+0x618,seed)
    if engine.trace then engine.trace.rngReturnAddresses=rngReturnAddresses end
    local recorder=Session:new(engine,config)
    self.recorder=recorder
    engine:install(recorder)
    if engine.trace then
      require('code/network-observer').install(engine.trace)
      require('code/rng-observer').install(engine.trace)
      require('code/world-hash-observer').install(engine.trace)
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
    observe(native.addr(0x442877),5,function() recorder:beginMatch() end)
    observe(native.addr(0x4428c6),10,function()
      if engine.trace then engine.trace:observe('stop','new match') end
      recorder:prepareRecording()
      ui.resetButtons()
    end)
    observe(native.addr(0x46b358),6,function(registers)
      if registers.EBP==61 and not engine.loading then recorder:reset(); ui.resetButtons() end
    end)
    observe(native.addr(0x495337),6,function()
      if not engine.loading then recorder:reset() end
    end)
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
    fixes.installTick(sites.tick,engine.scope,engine.base+0x618,recorder.halt,tickCallback,multiplayerTick)
  end)
end

function module:enable(config)
  return require('code/startup').run(function(stage) return enable(self,config,stage) end)
end

function module:disable()
  if self.recorder then self.recorder:reset() end
end
return module
