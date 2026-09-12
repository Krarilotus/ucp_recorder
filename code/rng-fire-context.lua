-- Inputs to the two fire-admission routines, at their existing RNG2 call.
-- This observes the caller and arguments; it neither ignites nor suppresses fire.
local M={}
local binding,guards
function M.verify()
 local check=require('code/hook-check')
 if not binding then
  local rng=require('code/rng-bindings').resolve()
  local calls,g={},{}
  for _,kind in ipairs({'ignite','spread'}) do
   local site=check.resolve(require('code/attribution-patterns')[kind],'Recorder RNG '..kind..' caller')
   local a=site.address
   assert(core.readInteger(a+5)==rng.state+2 and core.readInteger(a+11)==rng.state
    and a+20+core.readInteger(a+16)==rng.streams[2].address,
    'Recorder fire caller disagrees with the RNG owner')
   assert(core.readInteger(a+45)==core.readInteger(a+38)+4,
    'Recorder fire coordinate table layout is unavailable')
   calls[a+20]=kind;g[kind]=site
  end
  assert(core.readInteger(g.ignite.address+38)==core.readInteger(g.spread.address+38)
   and core.readInteger(g.ignite.address+101)==core.readInteger(g.spread.address+109),
   'Recorder fire callers disagree on their native coordinate/tile tables')
  binding=calls;guards=g
 end
 for _,site in pairs(guards) do check.verify(site,'RNG fire context is unavailable') end
 return binding
end
function M.read(profile,address,stack,tick)
 local kind=profile[address]
 if not kind then return end
 -- RNG return, saved EDI/ESI/EBP, caller, then six cdecl arguments.
 return {kind=kind,time=tick,caller=core.readInteger(stack+16)%4294967296,
  player=core.readInteger(stack+20),microX=core.readInteger(stack+24),
  microY=core.readInteger(stack+28),height=core.readInteger(stack+32),
  spreadParameter=core.readInteger(stack+36),intensity=core.readInteger(stack+40)}
end
return M
