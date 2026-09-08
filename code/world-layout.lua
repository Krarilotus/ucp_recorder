-- Native section schema shared by live capture and recorded-file validation.
-- Decode descriptors only; the caller owns any memory or disk access.
local profiles=require('code/world-sections')
local M={}

local function unsigned(data,offset,size)
  local value=0
  for i=size,1,-1 do value=value*256+assert(data:byte(offset+i)) end
  return value
end

---@class NativeWorldSection
---@field address integer
---@field size integer
---@field section integer
---@field compressed integer
---@field offset integer
---@field sha256 string|nil
---@param raw string
---@param variant string
---@return NativeWorldSection[]
---@return table profile
function M.decode(raw,variant)
  local profile=assert(profiles[variant],'Unsupported world capture executable')
  assert(type(raw)=='string' and #raw==profile.bytes and sha.sha256(raw)==profile.hash,
    'Native save section table changed')
  local entries,total={},0
  for offset=0,#raw-17,16 do
    local address,skip,size=unsigned(raw,offset,4),unsigned(raw,offset+4,4),unsigned(raw,offset+8,4)
    assert(address>=0x400000 and size>0 and size<=32*1024*1024 and address+size<0x80000000,
      'Invalid native save section range')
    if skip==0 then
      entries[#entries+1]={address=address,size=size,section=unsigned(raw,offset+14,2),
        compressed=unsigned(raw,offset+12,2),offset=total}
      total=total+size
    end
  end
  assert(unsigned(raw,#raw-16,4)==0 and total==profile.total,'Invalid native save section ending')
  return entries,profile
end
return M
