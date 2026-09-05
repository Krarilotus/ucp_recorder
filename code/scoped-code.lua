-- Small x86 emitter for gates whose original instructions contain relative
-- branches/calls. core.insertCode copies bytes without relocating them.
local M={}
local function dword(out,value)
  value=value%4294967296
  for _=1,4 do out[#out+1]=value%256; value=math.floor(value/256) end
end

function M.jump(from,to,size)
  local bytes={0xe9}; dword(bytes,to-from-5)
  for i=6,size do bytes[i]=0x90 end
  return bytes
end

function M.build(site,enabled,mode,seed,origin)
  local out,labels,refs={},{},{}
  local function emit(...) for _,value in ipairs({...}) do out[#out+1]=value end end
  local function rel(op,target)
    for _,byte in ipairs(op) do emit(byte) end
    if type(target)=='string' then refs[#refs+1]={offset=#out,target=target}; dword(out,0)
    else dword(out,target-origin-#out-4) end
  end
  local function compare(address,value) emit(0x83,0x3d); dword(out,address); emit(value) end
  emit(0x9c) -- pushfd: the conditional branches below must preserve incoming flags
  compare(enabled,1); rel({0x0f,0x85},'original')
  compare(mode,0); rel({0x0f,0x84},'patched')
  compare(mode,99); rel({0x0f,0x85},'original')
  labels.patched=#out; emit(0x9d)
  if site.patch=='cleanup' then emit(0x8d,0x64,0x24,0x2c) -- lea esp,[esp+44], no flag changes
  elseif site.patch=='taken' then rel({0xe9},site.target)
  elseif site.patch=='fallthrough' then for i=3,#site.bytes do emit(site.bytes[i]) end
  elseif site.patch=='seed' then
    emit(0xb8); dword(out,seed)
    for _,byte in ipairs(site.bytes) do emit(byte) end
  elseif site.patch=='tick' then
    emit(0x9c,0x60) -- preserve flags and registers across the Lua observer
    rel({0xe8},site.callback)
    emit(0x61)
    compare(site.halt,0); rel({0x0f,0x85},'halted')
    emit(0x9d)
    for _,byte in ipairs(site.bytes) do emit(byte) end
    rel({0xe9},site.address+#site.bytes)
    labels.halted=#out; emit(0x9d); rel({0xe9},site.skipTick)
  end
  rel({0xe9},site.address+#site.bytes)
  labels.original=#out; emit(0x9d)
  if site.patch=='tick' and site.originalCallback then
    emit(0x9c,0x60)
    rel({0xe8},site.originalCallback)
    emit(0x61,0x9d)
  end
  if site.kind=='call' then rel({0xe8},site.target)
  elseif site.kind=='branch' then
    rel({0x0f,site.condition},site.target)
    for i=3,#site.bytes do emit(site.bytes[i]) end
  else for _,byte in ipairs(site.bytes) do emit(byte) end end
  rel({0xe9},site.address+#site.bytes)
  for _,ref in ipairs(refs) do
    local encoded={}; dword(encoded,assert(labels[ref.target])-ref.offset-4)
    for i,byte in ipairs(encoded) do out[ref.offset+i]=byte end
  end
  return out
end
return M
