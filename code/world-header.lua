-- Non-section save metadata read by FilePackager::readMapOrSavFile. These fields
-- are absent from the 122-section world snapshot. Keep the native writer's order.
local M={BYTES=2141}
---@class NativeHeaderPart
---@field size integer
---@field operand integer Offset of the native writer's PUSH data operand.
---@class NativeHeaderGroup
---@field name string
---@field parts NativeHeaderPart[]
---@field pattern string Verified native writer block, including field lengths.
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
  {name='description',pattern='83 C4 18 55 68 ? ? ? ? 68 E8 03 00 00 B9 ? ? ? ? E8 ? ? ? ? 6A 04 8D 4C 24 28 51 83 C0 08 57 89 44 24 30 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 8B 54 24 48 83 C2 F8 52 55 57 E8 ? ? ? ?',
    parts={{size=4,operand=47},{size=4,operand=60},{size=1000,operand=5}}},
  {name='timeAndHash',pattern='6A 04 8D 44 24 58 50 57 C7 44 24 60 08 00 00 00 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 83 C4 48 6A 04 68 ? ? ? ? 57 E8 ? ? ? ?',
    parts={{size=4,operand=24},{size=4,operand=40}}},
  {name='players',pattern='6A 04 8D 4C 24 34 51 57 C7 44 24 3C 1C 00 00 00 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 14 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ?',
    parts={{size=4,operand=24},{size=20,operand=37},{size=4,operand=50}}},
  {name='scenario',pattern='6A 04 8D 54 24 64 52 57 C7 44 24 6C F9 03 00 00 E8 ? ? ? ? 83 C4 48 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 68 E9 03 00 00 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ?',
    parts={{size=4,operand=27},{size=4,operand=40},{size=4,operand=53},{size=1001,operand=69},{size=4,operand=82}}},
  {name='skirmish',pattern='6A 04 8D 44 24 64 50 57 C7 44 24 6C 50 00 00 00 E8 ? ? ? ? 83 C4 48 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 04 68 ? ? ? ? 57 E8 ? ? ? ? 6A 40 68 ? ? ? ? 57 E8 ? ? ? ?',
    parts={{size=4,operand=27},{size=4,operand=40},{size=4,operand=53},{size=4,operand=66},{size=64,operand=79}}},
}
local bindings

local function resolve()
  if bindings then return bindings end
  local result={}
  for i,group in ipairs(groups) do
    local ok,address=pcall(core.AOBScan,group.pattern)
    assert(ok and type(address)=='number' and address>0,'Cannot resolve native save header '..group.name)
    local second=core.scanForAOB(group.pattern,address+1)
    assert(second==nil or second==0,'Ambiguous native save header '..group.name)
    local tokens={}
    for token in group.pattern:gmatch('%S+') do tokens[#tokens+1]=token end
    local bytes=core.readBytes(address,#tokens)
    for j,token in ipairs(tokens) do
      assert(token=='?' or bytes[j]==tonumber(token,16),'Modified native save header '..group.name)
    end
    local parts={}
    for j,part in ipairs(group.parts) do
      local pointer=core.readInteger(address+part.operand)
      require('code/validation').integer(pointer,0x10000,0x7fffffff-part.size,'Native save header pointer')
      parts[j]=pointer
    end
    result[i]={address=address,bytes=bytes,parts=parts}
  end
  -- These contiguous fields are passed separately by the native writer.
  assert(result[1].parts[2]==result[1].parts[1]+4 and result[1].parts[3]==result[1].parts[1]+8
    and result[2].parts[2]==result[2].parts[1]+4
    and result[3].parts[2]==result[3].parts[1]+4 and result[3].parts[3]==result[3].parts[1]+24
    and result[4].parts[2]==result[4].parts[1]+4,'Native save header operand layout differs')
  bindings=result
  return result
end

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
  local sites=resolve()
  -- Verify every reference before following any data address. Shared save-entry
  -- wrappers are left intact; this code neither calls nor modifies the writer.
  for i,group in ipairs(groups) do
    require('code/hook-check').verify(sites[i],'Native save header reference changed: '..group.name)
  end
  local chunks,fields,offset={},{},0
  for i,group in ipairs(groups) do
    local size=0
    for j,part in ipairs(group.parts) do
      local data=core.readString(sites[i].parts[j],part.size)
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
