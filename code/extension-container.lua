-- Custom save sections use map-extensions' ZIP format. Encoding only reads
-- supplied bytes; it never invokes the native save machinery or changes a world.
local M={MAX_BYTES=1024*1024}
local library
function M.encode(entries)
  if not library then
    local handle,reason=core.openLibraryHandle('ucp/modules/map-extensions-1.0.0/luamemzip.dll')
    assert(handle,reason); library=handle:require('luamemzip')
  end
  local zip=library:MemoryZip(nil,nil,'w')
  local ok,result=xpcall(function()
    local names,total={},0
    for name,data in pairs(entries) do
      assert(type(name)=='string' and name:match('^[%w_-]+/[%w_.-]+$') and not name:find('..',1,true),
        'Invalid extension save entry')
      assert(type(data)=='string','Invalid extension save data')
      total=total+#data; assert(total<=M.MAX_BYTES,'Extension state is too large')
      names[#names+1]=name
    end
    table.sort(names)
    for _,name in ipairs(names) do
      assert(zip:open_entry(name)); assert(zip:write_entry(entries[name])); assert(zip:close_entry())
    end
    local raw,size=zip:serialize()
    assert(type(raw)=='string' and #raw==size and size>0 and size<=M.MAX_BYTES,'Invalid custom world ZIP')
    return raw
  end,debug.traceback)
  local closed,reason=pcall(zip.close,zip)
  assert(ok,result); assert(closed,reason)
  return result
end
return M
