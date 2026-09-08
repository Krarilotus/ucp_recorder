-- Binary transfers for startup/library work, not simulation ticks. Older RPS
-- releases implement writeString as a C string copy and truncate embedded NULs.
local M={CHUNK=4096}
local writer
local function writeBytes(address,data)
  for offset=1,#data,M.CHUNK do
    core.writeBytes(address+offset-1,{data:byte(offset,math.min(offset+M.CHUNK-1,#data))})
  end
end

function M.prepare()
  if writer then return end
  local address=core.allocate(257,true) -- include a possible C string terminator
  local ok,result=pcall(function()
    local bytes={}; for i=0,255 do bytes[#bytes+1]=string.char(i) end
    local probe=table.concat(bytes)
    core.writeString(address,probe)
    local copy=core.readString(address,#probe)==probe and core.writeString or writeBytes
    copy(address,probe)
    assert(core.readString(address,#probe)==probe,'Binary memory transfer verification failed')
    return copy
  end)
  core.deallocate(address)
  assert(ok,result)
  writer=result
end

---@param address integer Caller-owned buffer with room for data and a terminator.
---@param data string Binary payload; no string terminator is part of its length.
function M.write(address,data)
  M.prepare()
  writer(address,data)
end
return M
