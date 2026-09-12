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
  assert(type(raw)=='string' and #raw==profile.bytes and #profile.entries==122,
    'Native save section table changed')
  local entries,total={},0
  for index,expected in ipairs(profile.entries) do
    local offset=(index-1)*16
    local address,skip,size=unsigned(raw,offset,4),unsigned(raw,offset+4,4),unsigned(raw,offset+8,4)
    assert(address>=0x400000 and size>0 and size<=32*1024*1024 and address+size<0x80000000,
      'Invalid native save section range')
    local section,compressed=unsigned(raw,offset+14,2),unsigned(raw,offset+12,2)
    assert(skip==0 and size==expected.size and section==expected.section
      and compressed==expected.compressed,'Native save section schema differs at '..index)
    entries[#entries+1]={address=address,size=size,section=section,compressed=compressed,offset=total}
    total=total+size
  end
  assert(raw:sub(-16)==string.rep('\0',16) and total==profile.total,'Invalid native save section ending')
  -- This is the captured table's integrity hash, not an address whitelist.
  return entries,{bytes=profile.bytes,total=total,hash=sha.sha256(raw)}
end
return M
