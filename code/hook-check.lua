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
return M
