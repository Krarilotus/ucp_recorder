-- Use map-extensions' existing ZIP implementation and published entry format.
-- Do not invoke serializers against the current game when converting a recording.
local adapter=require('code/automarket-replay')
local M={}
local library

function M.encode(data,descriptor)
  adapter.descriptor(descriptor)
  assert(adapter.compatible(descriptor) and adapter.saveHookAvailable(),
    'Preparing Automarket requires its recorded adapter and map-extensions')
  assert(type(data)=='string' and #data==2416 and data:sub(1,4)=='\2\0\0\0',
    'Invalid Automarket snapshot')
  if not library then
    local handle,reason=core.openLibraryHandle('ucp/modules/map-extensions-1.0.0/luamemzip.dll')
    assert(handle,reason)
    library=handle:require('luamemzip')
  end
  local zip=library:MemoryZip(nil,nil,'w')
  local ok,result=xpcall(function()
    assert(zip:open_entry('automarket/automarketplayerdata.bin'))
    assert(zip:write_entry(data)); assert(zip:close_entry())
    local raw,size=zip:serialize()
    assert(type(raw)=='string' and #raw==size and size>0 and size<65536,'Invalid custom world ZIP')
    return raw
  end,debug.traceback)
  local closed,reason=pcall(zip.close,zip)
  assert(ok,result); assert(closed,reason)
  return result
end
return M
