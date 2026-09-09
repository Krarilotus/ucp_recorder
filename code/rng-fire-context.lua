-- Inputs to the two fire-admission routines, at their existing RNG2 call.
-- This observes the caller and arguments; it neither ignites nor suppresses fire.
local M={
 SHC={
  {address=0x4052E0,kind='ignite',bytes={85,86,15,191,53,194,121,162,1,87,185,192,121,162,1,232,220,84,6,0}},
  {address=0x4054E0,kind='spread',bytes={85,86,15,191,53,194,121,162,1,87,185,192,121,162,1,232,220,82,6,0}},
 },
 Extreme={
  {address=0x4052F0,kind='ignite',bytes={85,86,15,191,53,194,174,75,2,87,185,192,174,75,2,232,236,86,6,0}},
  {address=0x4054F0,kind='spread',bytes={85,86,15,191,53,194,174,75,2,87,185,192,174,75,2,232,236,84,6,0}},
 },
}
function M.verify(variant)
 local calls={}
 for _,site in ipairs(assert(M[variant],'Unsupported fire context profile')) do
  require('code/hook-check').verify(site,'RNG fire context is unavailable')
  calls[site.address+#site.bytes]=site.kind
 end
 return calls
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
