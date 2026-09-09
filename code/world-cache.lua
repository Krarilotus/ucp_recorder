-- Trust only conversions produced by this process. Files supplied with a replay
-- cannot establish that a native save was derived from its captured source.
-- The caller still validates source sections on a hit. Keep at most one recovery
-- chain's worth of proofs; eviction changes preparation cost, never correctness.
local M={REVISION=1}
local entries,order={},{}
local function copy(value)
  local result={}; for key,item in pairs(value) do result[key]=item end; return result
end

function M.remember(path,entry)
  if not entries[path] then
    order[#order+1]=path
    if #order>32 then entries[table.remove(order,1)]=nil end
  end
  entries[path]=copy(entry)
end

function M.load(path,reader,profile,limit)
  local entry=entries[path]
  if not entry or entry.converterRevision~=M.REVISION
    or entry.sourceWorldHash~=reader.capture.world.hash
    or entry.variant~=profile.name or entry.executable~=profile.sha256 then return end
  local ok,value=pcall(function()
    assert(entry.bytes<=limit)
    local size=0
    local hash=require('code/native-hash').file(path..'/world-native.sav',limit,
      function(_,count) size=count end)
    assert(size==entry.bytes and hash==entry.sha256)
    return copy(entry)
  end)
  if ok then return value end
end
return M
