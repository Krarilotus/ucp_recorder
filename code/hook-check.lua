-- Keep byte guards strict and make conflicting patches identifiable in reports.
local M={}
local function hex(bytes,count,skip)
  local parts={}
  for i=1,count do
    parts[i]=i<=(skip or 0) and '**' or
      (type(bytes[i])=='number' and string.format('%02X',bytes[i]) or '??')
  end
  return table.concat(parts,' ')
end
function M.verify(site,label,actual,skip)
  actual=actual or core.readBytes(site.address,#site.bytes)
  for i,value in ipairs(site.bytes) do
    if i>(skip or 0) and actual[i]~=value then
      error(string.format('%s at 0x%08X; expected [%s], found [%s]',label,
        site.address,hex(site.bytes,#site.bytes,skip),hex(actual,#site.bytes)),0)
    end
  end
end
-- Framework discovery/cache plus explicit uniqueness and current instruction
-- context. Retain these bytes for the existing pre-install conflict check.
function M.resolve(pattern,label)
  local ok,address=pcall(core.AOBScan,pattern)
  assert(ok and type(address)=='number' and address>0,label..': native context not found')
  local second=core.scanForAOB(pattern,address+1)
  assert(second==nil or second==0,label..': ambiguous native context')
  return M.context(address,pattern,label)
end
function M.context(address,pattern,label)
  local tokens={}
  for token in pattern:gmatch('%S+') do tokens[#tokens+1]=token end
  local bytes=core.readBytes(address,#tokens)
  for i,token in ipairs(tokens) do
    assert(token=='?' or bytes[i]==tonumber(token,16),label..': modified native context')
  end
  return {address=address,bytes=bytes}
end
return M
