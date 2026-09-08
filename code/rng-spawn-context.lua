-- Read-only context at spawnUnit's existing RNG call. No additional native hook.
local M={
  SHC={entry=0x53E440,call=0x53E5C6,callBytes={232,5,194,242,255}},
  Extreme={entry=0x53E860,call=0x53E9E6,callBytes={232,5,192,242,255}},
}
local prologue={83,139,217,185,1,0,0,0,87,139,249}

function M.verify(variant)
  local profile=assert(M[variant],'Unsupported spawn context profile')
  for _,site in ipairs({{address=profile.entry,bytes=prologue},
      {address=profile.call,bytes=profile.callBytes}}) do
    require('code/hook-check').verify(site,'RNG spawn context is unavailable')
  end
  return profile
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
