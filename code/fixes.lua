local native=require('code/native')
local profiles=require('code/scoped-sites')
local emitter=require('code/scoped-code')
local M={}

function M.verify()
  local sites=assert(profiles[native.profile.name])
  for _,site in ipairs(sites) do
    local actual=core.readBytes(site.address,#site.bytes)
    for i,byte in ipairs(site.bytes) do
      assert(actual[i]==byte,'Recorder simulation hook conflicts at '..site.name)
    end
  end
  return sites
end

function M.install(sites,enabled,mode,seed)
  for _,site in ipairs(sites) do
    if site.kind~='seed' or seed~=nil then
      local size=#emitter.build(site,enabled,mode,seed,0)
      local target=core.allocateCode(size)
      core.writeCode(target,emitter.build(site,enabled,mode,seed,target))
      core.writeCode(site.address,emitter.jump(site.address,target,#site.bytes))
    end
  end
end

function M.installTick(site,enabled,mode,halt,callback,originalCallback)
  local tick={address=site.address,bytes=site.bytes,kind='raw',patch='tick',
    halt=halt,callback=callback,originalCallback=originalCallback,skipTick=site.address+0x25}
  M.install({tick},enabled,mode)
end
return M
