-- A native save is derived from a verified captured world. Reuse it only when
-- its source identity, converter revision and entire output digest still match.
-- The caller must validate source sections even on a hit; cache files are not
-- an alternative source of truth for the recording.
local M={REVISION=1}

function M.load(path,reader,profile,limit)
  local ok,value=pcall(function()
    local raw=require('code/world-reader').read(path..'/world-native.json',4096)
    local entry=json:decode(raw)
    assert(type(entry)=='table' and entry.converterRevision==M.REVISION
      and entry.format==1 and entry.sourceWorldHash==reader.capture.world.hash
      and entry.variant==profile.name and entry.executable==profile.sha256)
    local valid=require('code/validation')
    valid.hash(entry.sha256,'prepared world hash')
    valid.integer(entry.bytes,3036,limit,'prepared world size')
    valid.integer(entry.payloadBytes,1,limit,'prepared world payload')
    valid.integer(entry.sections,1,150,'prepared world sections')
    local size=0
    local hash=require('code/native-hash').file(path..'/world-native.sav',limit,
      function(_,count) size=count end)
    assert(size==entry.bytes and hash==entry.sha256)
    return entry
  end)
  if ok then return value end
end
return M
