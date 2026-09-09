-- Binary transfers for startup/library work, not simulation ticks. Older RPS
-- releases implement writeString as a C string copy and truncate embedded NULs.
local M={CHUNK=4096}
local writer
local function writeBytes(address,data)
  for offset=1,#data,M.CHUNK do
    core.writeBytes(address+offset-1,{data:byte(offset,math.min(offset+M.CHUNK-1,#data))})
  end
end

-- CFFI is provided by the UI dependency. Its explicit length avoids both the
-- legacy C-string truncation and building a Lua number table for every chunk.
-- Probe the loaded bridge rather than infer its behavior from a version number.
local function nativeCopy()
  if not (modules and modules.cffi) then return end
  local ffi=modules.cffi:cffi()
  if not (ffi and ffi.cast and ffi.copy) then return end
  return function(address,data) ffi.copy(ffi.cast('void *',address),data,#data) end
end

function M.prepare()
  if writer then return end
  local address=core.allocate(257,true) -- include a possible C string terminator
  local ok,result=pcall(function()
    local bytes={}; for i=0,255 do bytes[#bytes+1]=string.char(i) end
    local probe=table.concat(bytes)
    local function verified(copy)
      if not copy then return false end
      return pcall(function()
        -- Two different patterns prevent a failed candidate's leftover bytes
        -- from making a no-op fallback appear to work.
        for _,data in ipairs({probe,probe:reverse()}) do
          local blank=string.rep('\165',#data)
          copy(address,blank)
          assert(core.readString(address,#blank)==blank,'Binary reset differs')
          copy(address,data)
          assert(core.readString(address,#data)==data,'Binary copy differs')
        end
      end)
    end
    local available,copy=pcall(nativeCopy)
    if available and verified(copy) then return copy end
    if verified(core.writeString) then return core.writeString end
    assert(verified(writeBytes),'Binary memory transfer verification failed')
    return writeBytes
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
