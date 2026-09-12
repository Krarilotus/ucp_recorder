-- Replay scope keeps native simulation RNG separate from presentation-only
-- callers. Use the original calls outside scope; do not add an RNG or timer.
local M={}
local binding,guards,seedSite
local dustPattern='83 EC 08 53 8B 5C 24 34 83 FB 2B 56 8B F1 89 74 24 0C C7 44 24 08 00 00 00 00 7E 05 83 FB 5B 7C 05 83 FB 5E 7E 0A 5E 33 C0 5B 83 C4 08 C2 2C 00'
function M.resolve(seed)
  local check=require('code/hook-check')
  local rng=require('code/rng-bindings').resolve()
  if not binding then
    local result,g={},{}
    local commands=require('code/native-command').bind({}).commands
    local state=require('code/engine-state-sites').resolve()
    local owners={mode=commands.handler+0x618,player=commands.localPlayer,tick=commands.tick,gameCore=state.gameCore}
    for _,context in ipairs(require('code/scoped-contexts')) do
      local guard=check.resolve(context.pattern,'Recorder replay scope '..context.name)
      g[context.name]=guard
      for _,field in ipairs(context.rngFields) do
        assert(core.readInteger(guard.address+field[1])==rng.state+field[2],
          'Recorder replay scope has a different RNG owner: '..context.name)
      end
      for _,field in ipairs(context.ownerFields) do
        assert(core.readInteger(guard.address+field[1])==owners[field[2]],
          'Recorder replay scope disagrees with '..field[2]..': '..context.name)
      end
      for _,spec in ipairs(context.sites) do
        local address=guard.address+spec.offset
        local site={name=spec.name,address=address,bytes=core.readBytes(address,spec.size),guard=guard,
          kind=spec.kind,patch=spec.patch,condition=spec.condition}
        if spec.kind=='call' or spec.kind=='tail' then
          site.target=address+5+core.readInteger(address+1)
          if spec.stream then
            assert(site.target==rng.streams[spec.stream].address,
              'Recorder replay scope calls a different RNG stream: '..spec.name)
          else
            assert(spec.name=='dustEntity','Unknown replay scope native callee')
            g.dustCallee=check.context(site.target,dustPattern,'Recorder native dust allocation ABI')
          end
        elseif spec.kind=='branch' then
          local distance=site.bytes[2]
          site.target=address+2+(distance>=128 and distance-256 or distance)
        end
        result[#result+1]=site
      end
    end
    for name,control in pairs(require('code/engine-state-sites').controls()) do
      local site={name=name}
      for key,value in pairs(control) do site[key]=value end
      result[#result+1]=site;g[name]=control.guard
    end
    binding=result;guards=g
  end
  if seed~=nil and not seedSite then
    local guard=require('code/rng-bindings').seed()
    seedSite={name='seed',address=guard.address+10,bytes=core.readBytes(guard.address+10,6),
      guard=guard,kind='seed',patch='seed'}
    binding[#binding+1]=seedSite
  end
  return binding
end
function M.verify(seed)
  local result=M.resolve(seed)
  for name,guard in pairs(guards) do
    require('code/hook-check').verify(guard,'Recorder simulation context conflicts at '..name)
  end
  if seed~=nil then require('code/hook-check').verify(seedSite.guard,'Recorder simulation hook conflicts at seed') end
  return result
end
return M
