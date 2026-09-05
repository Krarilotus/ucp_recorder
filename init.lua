local native=require('code/native')
local Engine=require('code/engine')
local Session=require('code/session-recorder')
local module={}

function module:enable(config)
  native.verify()
  local sites=Engine.verify()
  local seed
  if config.useFixedSeed then
    seed=require('code/validation').integer(config.fixedSeed,-2147483648,2147483647,'fixed seed')
  end
  require('code/sessions').captureSettings()
  require('code/fixes').apply()
  local engine=Engine.new(sites)
  local recorder=Session:new(engine)
  self.recorder=recorder
  engine:install(recorder)
  local ui=require('code/ui')
  ui.createButtons(recorder)

  local function observe(address,size,callback)
    core.detourCode(function(registers)
      recorder:guard(function() callback(registers) end)
      return registers
    end,address,size)
  end
  observe(native.addr(0x4428c6),10,function()
    recorder:activateRecording()
    ui.resetButtons()
  end)
  observe(native.addr(0x487c50),6,function(registers)
    if recorder.active and recorder.mode=='record' then recorder:onTransmitCommand(registers) end
  end)
  observe(native.addr(0x490690),8,function() recorder:feed() end)
  observe(native.addr(0x46b358),6,function(registers)
    if registers.EBP==61 and not engine.loading then recorder:reset(); ui.resetButtons() end
  end)
  observe(native.addr(0x495337),6,function()
    if not engine.loading then recorder:reset() end
  end)
  observe(native.addr(0x494ba5),5,function() recorder:reset() end)

  local tickCallback=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xC3})
  observe(tickCallback,5,function() recorder:onTick() end)
  core.insertCode(sites.tick.address,5,{
    core.AssemblyLambda([[
      pushfd
      pushad
      call callback
      popad
      cmp dword [halt], 0
      je continueTick
      popfd
      jmp skipTick
    continueTick:
      popfd
    ]],{callback=tickCallback,halt=recorder.halt,skipTick=sites.tick.address+0x25})
  },nil,'after')
  if seed then
    core.detourCode(function(registers)
      registers.EAX=seed
      return registers
    end,native.addr(0x46a74a),6)
  end
end

function module:disable()
  if self.recorder then self.recorder:reset() end
end
return module
