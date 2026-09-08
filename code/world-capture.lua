-- Read native save sections; never call the native multiplayer save routine.
local native=require('code/native')
local sections=require('code/world-sections')
local store=require('code/sessions')
local M={CHUNK=65536}

local function unsigned(data,offset,size)
  local value=0
  for i=size,1,-1 do value=value*256+assert(data:byte(offset+i)) end
  return value
end

function M.layout()
  local profile=assert(sections[native.profile.name],'Unsupported world capture executable')
  local raw=core.readString(profile.address,profile.bytes)
  assert(#raw==profile.bytes and sha.sha256(raw)==profile.hash,'Native save section table changed')
  local entries,total={},0
  for offset=0,#raw-17,16 do
    local address,skip,size=unsigned(raw,offset,4),unsigned(raw,offset+4,4),unsigned(raw,offset+8,4)
    assert(address>=0x400000 and size>0 and size<=32*1024*1024 and address+size<0x80000000,
      'Invalid native save section range')
    if skip==0 then
      entries[#entries+1]={address=address,size=size,section=unsigned(raw,offset+14,2),
        compressed=unsigned(raw,offset+12,2),offset=total}
      total=total+size
    end
  end
  assert(unsigned(raw,#raw-16,4)==0 and total==profile.total,'Invalid native save section ending')
  return entries,profile,raw
end

function M.capture(path,engine)
  local entries,profile,raw=M.layout()
  local manifest={format=1,kind='native-world-evidence',variant=native.profile.name,
    executable=native.profile.sha256,tick=engine:tick(),status='writing',playable=false,
    tableHash=profile.hash,bytes=profile.total,sections=entries,
    omissions={'native-save-container-and-load-fixups','unserialized-network-runtime',
      'unregistered-extension-state','resynchronization-world-restoration'}}
  store.write(path..'/world.json',json:encode(manifest))
  store.write(path..'/world-layout.bin',raw)
  local file=assert(io.open(path..'/world.bin','wb'))
  local ok,reason=pcall(function()
    for _,entry in ipairs(entries) do
      local chunks={}
      for offset=0,entry.size-1,M.CHUNK do
        local size=math.min(M.CHUNK,entry.size-offset)
        local data=core.readString(entry.address+offset,size)
        assert(type(data)=='string' and #data==size,'Short native world read')
        assert(file:write(data)); chunks[#chunks+1]=data
      end
      entry.sha256=sha.sha256(table.concat(chunks))
    end
    assert(file:flush())
  end)
  local closed=file:close()
  assert(ok and closed,reason or 'Cannot close world capture')
  -- Automarket exposes this pointer as part of its enabled module object.
  -- Reading its exact save payload avoids calling map-extensions callbacks,
  -- which would update custom native section memory and write cache files.
  local adapter=require('code/automarket-replay')
  local descriptor=adapter.current()
  if descriptor then
    local pointer=modules.automarket.pAutomarketData
    require('code/validation').integer(pointer,0x10000,0x7fffffff-2416,'Automarket data pointer')
    local data=core.readString(pointer,2416)
    assert(#data==2416 and unsigned(data,0,4)==2,'Unsupported Automarket saved data layout')
    store.write(path..'/automarket.bin',data)
    manifest.automarket={version=descriptor.version,protocol=descriptor.protocol,
      format=2,bytes=#data,sha256=sha.sha256(data)}
  end
  assert(engine:tick()==manifest.tick,'Simulation advanced during world capture')
  manifest.status='complete'
  local encoded=json:encode(manifest)
  store.write(path..'/world.json.tmp',encoded)
  require('code/platform').replace(path..'/world.json.tmp',path..'/world.json')
  return {status='complete',hash=sha.sha256(encoded),bytes=profile.total,
    automarket=manifest.automarket~=nil}
end
return M
