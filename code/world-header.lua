-- Non-section save metadata read by FilePackager::readMapOrSavFile. These fields
-- are absent from the 122-section world snapshot. Keep the native writer's order.
local native=require('code/native')
local M={BYTES=2141}
---@class NativeHeaderPart
---@field size integer
---@field shc integer
---@field extreme integer
---@field reference integer SHC PUSH operand site; Extreme is +0x230.
---@class NativeHeaderGroup
---@field name string
---@field parts NativeHeaderPart[]
---@class CapturedHeaderField
---@field name string
---@field offset integer
---@field size integer
---@class CapturedWorldHeader
---@field format integer
---@field bytes integer
---@field sha256 string
---@field fields CapturedHeaderField[]
---@field preview string
---@field timeAndHash string
---@type NativeHeaderGroup[]
local groups={
  {name='description',parts={
    {size=4,shc=0x1fe8678,extreme=0x2a7bb78,reference=0x474775},
    {size=4,shc=0x1fe867c,extreme=0x2a7bb7c,reference=0x474782},
    {size=1000,shc=0x1fe8680,extreme=0x2a7bb80,reference=0x47474b}}},
  {name='timeAndHash',parts={
    {size=4,shc=0x1a269bc,extreme=0x24b9ebc,reference=0x4747b3},
    {size=4,shc=0x1a269c0,extreme=0x24b9ec0,reference=0x4747c3}}},
  {name='players',parts={
    {size=4,shc=0x1fe9244,extreme=0x2a7c744,reference=0x4747e5},
    {size=20,shc=0x1fe9248,extreme=0x2a7c748,reference=0x4747f2},
    {size=4,shc=0x1fe925c,extreme=0x2a7c75c,reference=0x4747ff}}},
  {name='scenario',parts={
    {size=4,shc=0x1666d8c,extreme=0x1f99dd4,reference=0x474824},
    {size=4,shc=0x1666d90,extreme=0x1f99dd8,reference=0x474831},
    {size=4,shc=0x1fe9aa0,extreme=0x2a7cfa0,reference=0x47483e},
    {size=1001,shc=0x1fe8a68,extreme=0x2a7bf68,reference=0x47484e},
    {size=4,shc=0x1fe9aac,extreme=0x2a7cfac,reference=0x47485b}}},
  {name='skirmish',parts={
    {size=4,shc=0x1fe923c,extreme=0x2a7c73c,reference=0x474880},
    {size=4,shc=0x1fe7d88,extreme=0x2a7b288,reference=0x47488d},
    {size=4,shc=0x1a26a08,extreme=0x24b9f08,reference=0x47489a},
    {size=4,shc=0x1fe9260,extreme=0x2a7c760,reference=0x4748a7},
    {size=64,shc=0x1a930d4,extreme=0x25265d4,reference=0x4748b4}}},
}

function M.validate(data,descriptor)
  assert(type(data)=='string' and #data==M.BYTES and type(descriptor)=='table'
    and descriptor.format==1 and descriptor.bytes==M.BYTES
    and descriptor.sha256==sha.sha256(data),'Native save header is damaged')
  assert(type(descriptor.fields)=='table' and #descriptor.fields==#groups,'Native save header fields differ')
  local offset=0
  for i,group in ipairs(groups) do
    local size=0
    for _,part in ipairs(group.parts) do size=size+part.size end
    local field=descriptor.fields[i]
    assert(type(field)=='table' and field.name==group.name and field.offset==offset
      and field.size==size,'Native save header field differs: '..group.name)
    offset=offset+size
  end
end

---@return string data Raw metadata, without compression or section-size prefixes.
---@return CapturedWorldHeader descriptor
function M.read()
  local variant=native.profile.name
  assert(variant=='SHC' or variant=='Extreme','Unsupported native header layout')
  local index,delta=variant=='SHC' and 'shc' or 'extreme',variant=='SHC' and 0 or 0x230
  -- Verify every reference before following any data address. Shared save-entry
  -- wrappers are left intact; this code neither calls nor modifies the writer.
  for _,group in ipairs(groups) do
    for _,part in ipairs(group.parts) do
      local operand=part.reference+delta
      assert(core.readByte(operand)==0x68 and core.readInteger(operand+1)%4294967296==part[index],
        'Native save header reference changed: '..group.name)
    end
  end
  local chunks,fields,offset={},{},0
  for _,group in ipairs(groups) do
    local size=0
    for _,part in ipairs(group.parts) do
      local data=core.readString(part[index],part.size)
      assert(type(data)=='string' and #data==part.size,'Short native save header read: '..group.name)
      chunks[#chunks+1]=data
      size=size+part.size
    end
    fields[#fields+1]={name=group.name,offset=offset,size=size}
    offset=offset+size
  end
  assert(offset==M.BYTES,'Native header layout size differs')
  local data=table.concat(chunks)
  return data,{format=1,bytes=#data,sha256=sha.sha256(data),fields=fields,
    preview='not-captured',timeAndHash='native-cached-values'}
end
return M
