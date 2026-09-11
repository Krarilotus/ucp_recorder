-- Own the last observed RNG/resources independently of the mutable game world.
-- One allocation and one native copy call replace per-tick Lua strings/tables.
-- Each recorder retains this buffer across matches; only publication/checkpoints
-- materialize strings. No game code, hashing, I/O or callbacks run in the copier.
local M={RNG_BYTES=0x9c50,RESOURCE_BYTES=800}
local Boundary={}

function M.new(engine)
  local buffer=core.allocate(M.RNG_BYTES+M.RESOURCE_BYTES+1,true)
  local code={0x9c,0x56,0x57,0x51,0xfc,0xbf} -- pushfd; save esi/edi/ecx; cld; mov edi
  local function integer(value)
    value=math.floor(value) -- RPS writeCode requires integer-typed bytes in Lua 5.4.
    for _=1,4 do code[#code+1]=value%256; value=math.floor(value/256) end
  end
  integer(buffer)
  local function copy(source,bytes)
    code[#code+1]=0xbe; integer(source) -- mov esi, source
    code[#code+1]=0xb9; integer(bytes/4) -- mov ecx, DWORD count
    code[#code+1]=0xf3; code[#code+1]=0xa5 -- rep movsd; edi advances
  end
  copy(engine.rng,M.RNG_BYTES)
  for player=1,8 do copy(engine.sites.playerResources+player*0x39f4,100) end
  for _,byte in ipairs({0x59,0x5f,0x5e,0x9d,0xc3}) do code[#code+1]=byte end
  local address=core.allocateCode(#code)
  core.writeCode(address,code)
  return setmetatable({buffer=buffer,copy=core.exposeCode(address,0,0)}, {__index=Boundary})
end

function Boundary:clear() self.valid=false end

function Boundary:capture()
  self.copy()
  self.valid=true
end

function Boundary:read()
  assert(self.valid,'Missing observed recording boundary')
  return core.readString(self.buffer,M.RNG_BYTES),core.readString(self.buffer+M.RNG_BYTES,M.RESOURCE_BYTES)
end

function Boundary:rngState()
  assert(self.valid,'Missing observed recording boundary')
  local p=self.buffer
  return {core.readSmallInteger(p),core.readSmallInteger(p+2),
    core.readInteger(p+0x9c48),core.readInteger(p+0x9c4c)}
end

return M
