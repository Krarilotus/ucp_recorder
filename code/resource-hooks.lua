-- Resource lookup callers rely on ECX/EDX surviving these leaf functions.
-- A Lua hookCode wrapper only promises the public calling convention and can
-- clobber those registers. Keep both normal and override paths entirely native.
local jumps=require('code/scoped-code')
local M={}
function M.build(site,enabled,replacement,isFile,origin)
  local out,refs={},{ }
  local function emit(...) for _,b in ipairs({...}) do out[#out+1]=b end end
  local function dword(n)
    n=n%4294967296
    for _=1,4 do emit(n%256); n=math.floor(n/256) end
  end
  local function originalUnlessEqual()
    emit(0x0f,0x85); refs[#refs+1]=#out; dword(0)
  end
  emit(0x9c,0x83,0x3d); dword(enabled); emit(1); originalUnlessEqual()
  if isFile then
    emit(0x83,0xb9); dword(0xbc4); emit(1); originalUnlessEqual()
  end
  emit(0x9d,0xb8); dword(replacement)
  if isFile then emit(0xc3) else emit(0xc2,4,0) end
  local original=#out
  emit(0x9d)
  for _,b in ipairs(site.bytes) do emit(b) end
  local jump=jumps.jump(origin+#out,site.address+#site.bytes,5)
  for _,b in ipairs(jump) do emit(b) end
  for _,offset in ipairs(refs) do
    local value=original-offset-4
    for i=1,4 do out[offset+i]=value%256; value=math.floor(value/256) end
  end
  return out
end
function M.install(site,enabled,replacement,isFile)
  local target=core.allocateCode(#M.build(site,enabled,replacement,isFile,0))
  core.writeCode(target,M.build(site,enabled,replacement,isFile,target))
  core.writeCode(site.address,jumps.jump(site.address,target,#site.bytes))
end
return M
