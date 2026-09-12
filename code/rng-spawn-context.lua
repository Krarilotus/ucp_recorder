-- Read-only context at spawnUnit's existing RNG call. No additional native hook.
local M={}
local binding,guard
function M.verify()
  local check=require('code/hook-check')
  if not binding then
    local rng=require('code/rng-bindings').resolve()
    local commands=require('code/native-command').bind({}).commands
    local site=check.resolve(require('code/attribution-patterns').spawn,'Recorder RNG spawn caller')
    local a=site.address
    local capacity=core.readInteger(a+44)
    assert((capacity==2500 or capacity==10000) and core.readInteger(a+25)==capacity-1,
      'Recorder spawn context has an unsupported native unit capacity')
    assert(core.readInteger(a+60)==commands.tick+44 and core.readInteger(a+89)==commands.tick+44
      and core.readInteger(a+95)==commands.tick,
      'Recorder spawn context disagrees with the native clock/tag owner')
    assert(core.readInteger(a+375)==rng.state+2 and core.readInteger(a+386)==rng.state
      and a+395+core.readInteger(a+391)==rng.streams[2].address,
      'Recorder spawn context disagrees with the RNG owner')
    binding={entry=a,call=a+390,callBytes=core.readBytes(a+390,5)};guard=site
  end
  check.verify(guard,'RNG spawn context is unavailable')
  return binding
end

function M.read(profile,address,stack,tick)
  if address~=profile.call+5 then return end
  -- At RNG entry: return address, saved ESI/EBP/EDI/EBX, spawn caller,
  -- then spawnUnit's six original arguments. Verified on both executables.
  return {time=tick,caller=core.readInteger(stack+20)%4294967296,
    player=core.readInteger(stack+24),color=core.readInteger(stack+28),
    microX=core.readInteger(stack+32),microY=core.readInteger(stack+36),
    height=core.readInteger(stack+40),unitType=core.readInteger(stack+44)}
end
return M
