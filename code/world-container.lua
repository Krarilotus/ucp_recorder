-- Construct the native directory outside a match. No game world or transport
-- state is written; a prepared file is not by itself a playable MP replay.
local store=require('code/sessions')
local native=require('code/native')
local M={MAX_PAYLOAD=6000000}

---@class PreparedNativeWorld
---@field format integer
---@field sourceWorldHash string SHA-256 of the captured world manifest.
---@field variant string
---@field executable string
---@field sha256 string SHA-256 of the entire prepared native file.
---@field bytes integer
---@field payloadBytes integer
---@field sections integer
---@field preview string
---@field playable boolean Always false: conversion does not establish playback support.

local function word(value)
  require('code/validation').integer(value,0,4294967295,'Native container word')
  local bytes={}
  for i=1,4 do bytes[i]=string.char(value%256); value=math.floor(value/256) end
  return table.concat(bytes)
end

local function directory(entries,bytes)
  assert(#entries<=150,'Too many native world sections')
  local result={word(3036),word(bytes),word(#entries),word(172),string.rep('\0',16)}
  for _,field in ipairs({'size','storedSize','section','compressed','offset'}) do
    for i=1,150 do result[#result+1]=word(entries[i] and entries[i][field] or 0) end
  end
  result[#result+1]=word(0)
  local raw=table.concat(result)
  assert(#raw==3036,'Native directory size differs')
  return raw
end

local function header(reader,codec)
  -- A neutral preview is deliberate: capture does not invoke the native minimap
  -- renderer. The loader requires a nonzero first block to reach later metadata.
  local preview=assert(codec:compress(string.rep('\0',40512)),'Cannot encode native preview')
  local data=reader.header
  local description=assert(codec:compress(data:sub(9,1008)),'Cannot encode native description')
  local result={word(4294967295),word(#preview),preview,
    word(#description+8),data:sub(1,8),description}
  for i=2,#reader.manifest.header.fields do
    local field=reader.manifest.header.fields[i]
    result[#result+1]=word(field.size)
    result[#result+1]=data:sub(field.offset+1,field.offset+field.size)
  end
  result[#result+1]=word(0)
  return table.concat(result)
end

---@param path string Multiplayer capture folder.
---@param engine table
---@return PreparedNativeWorld
function M.prepare(path,engine,progress)
  local view=core.readInteger(engine.sites.gameCore+0xc)
  -- Conversion uses private codec buffers. Both single-player entry screens
  -- are safe; the native loader owns its later transition into the match.
  assert(engine:singlePlayer() and (view==20 or view==58),
    'Prepare multiplayer worlds from Skirmish or battle history')
  local reader=require('code/world-reader').open(path)
  local capacity=40512
  for _,entry in ipairs(reader.entries) do capacity=math.max(capacity,entry.size) end
  local result=require('code/world-codec').withBuffers(capacity,function(codec)
    local prefix=header(reader,codec)
    local file=assert(io.open(path..'/world-native.sav.tmp','wb'))
    local rows,bytes={},0
    local ok,reason=xpcall(function()
      assert(file:write(prefix,directory({},0)))
      local function section(id,data,compress)
        local packed=compress and codec:compress(data) or nil
        local payload=packed or data
        assert(bytes+#payload<=M.MAX_PAYLOAD,'Native world exceeds the original loader buffer')
        rows[#rows+1]={section=id,size=#data,storedSize=#payload,
          compressed=packed and 1 or 0,offset=bytes}
        assert(file:write(payload)); bytes=bytes+#payload
      end
      reader:eachSection(function(entry,data)
        section(entry.section,data,entry.compressed~=0)
        if progress then progress('Checking starting state...') end
      end)
      if reader.extensions then
        section(1337,reader.extensions,true)
      elseif reader.automarket then
        section(1337,require('code/automarket-container').encode(reader.automarket,reader.manifest.automarket),true)
      end
      assert(file:seek('set',#prefix)); assert(file:write(directory(rows,bytes)))
      assert(file:flush())
    end,debug.traceback)
    local closed=file:close()
    assert(ok and closed,reason or 'Cannot close prepared world')
    local data=require('code/world-reader').read(path..'/world-native.sav.tmp',M.MAX_PAYLOAD+110000)
    assert(#data==#prefix+3036+bytes,'Prepared native world length differs')
    return {format=1,sourceWorldHash=reader.capture.world.hash,variant=native.profile.name,
      executable=native.profile.sha256,sha256=require('code/native-hash').sha256(data),bytes=#data,
      payloadBytes=bytes,sections=#rows,preview='neutral-placeholder',playable=false}
  end)
  require('code/platform').replace(path..'/world-native.sav.tmp',path..'/world-native.sav')
  store.write(path..'/world-native.json.tmp',json:encode(result))
  require('code/platform').replace(path..'/world-native.json.tmp',path..'/world-native.json')
  return result
end
return M
