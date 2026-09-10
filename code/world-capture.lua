-- Read native save sections; never call the native multiplayer save routine.
local native=require('code/native')
local sections=require('code/world-sections')
local store=require('code/sessions')
local digest=require('code/native-hash')
local M={CHUNK=65536}

function M.layout()
  local profile=assert(sections[native.profile.name],'Unsupported world capture executable')
  local raw=core.readString(profile.address,profile.bytes)
  local entries=require('code/world-layout').decode(raw,native.profile.name)
  return entries,profile,raw
end

function M.extensionState()
  local market,marketInfo,extensionData,extensionInfo
  -- Automarket exposes this pointer as part of its enabled module object.
  -- Reading its exact save payload avoids calling map-extensions callbacks,
  -- which would update custom native section memory and write cache files.
  local adapter=require('code/automarket-replay')
  local descriptor=adapter.current()
  local custom={}
  if descriptor then
    local pointer=modules.automarket.pAutomarketData
    require('code/validation').integer(pointer,0x10000,0x7fffffff-2416,'Automarket data pointer')
    local data=core.readString(pointer,2416)
    assert(#data==2416 and data:sub(1,4)=='\2\0\0\0','Unsupported Automarket saved data layout')
    market=data
    marketInfo={version=descriptor.version,protocol=descriptor.protocol,
      format=2,bytes=#data,sha256=sha.sha256(data)}
    custom['automarket/automarketplayerdata.bin']=data
  end
  local legacy=modules and modules['ucp2-legacy']
  if legacy then
    assert(type(legacy.serializeSimulationState)=='function','UCP2 requires read-only simulation state export')
    legacy:serializeSimulationState({put=function(_,name,data)
      local path='ucp2-legacy/'..name
      assert(custom[path]==nil,'Duplicate UCP2 state entry'); custom[path]=data
    end})
  end
  if next(custom) then
    local raw=require('code/extension-container').encode(custom)
    extensionData=raw
    extensionInfo={bytes=#raw,sha256=sha.sha256(raw),ucp2=legacy~=nil}
  end
  return market,marketInfo,extensionData,extensionInfo
end

function M.capture(path,engine)
  digest.prepare()
  local entries,profile,raw=M.layout()
  local manifest={format=1,kind='native-world-evidence',variant=native.profile.name,
    executable=native.profile.sha256,tick=engine:tick(),status='writing',playable=false,
    tableHash=profile.hash,bytes=profile.total,sections=entries,
    omissions={'native-save-container-and-load-fixups','unserialized-network-runtime',
      'unregistered-extension-state','resynchronization-world-restoration'}}
  store.write(path..'/world.json',json:encode(manifest))
  store.write(path..'/world-layout.bin',raw)
  local header,descriptor=require('code/world-header').read()
  store.write(path..'/world-header.bin',header)
  manifest.header=descriptor
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
      entry.sha256=digest.sha256(table.concat(chunks))
    end
    assert(file:flush())
  end)
  local closed=file:close()
  assert(ok and closed,reason or 'Cannot close world capture')
  local market,marketInfo,extensions,extensionInfo=M.extensionState()
  if market then store.write(path..'/automarket.bin',market); manifest.automarket=marketInfo end
  if extensions then store.write(path..'/extensions.zip',extensions); manifest.extensions=extensionInfo end
  assert(engine:tick()==manifest.tick,'Simulation advanced during world capture')
  manifest.status='complete'
  local encoded=json:encode(manifest)
  store.write(path..'/world.json.tmp',encoded)
  require('code/platform').replace(path..'/world.json.tmp',path..'/world.json')
  return {status='complete',hash=sha.sha256(encoded),bytes=profile.total,
    automarket=manifest.automarket~=nil,extensions=manifest.extensions~=nil,header=true}
end
-- Called synchronously at a quiescent multiplayer simulation boundary. Unlike
-- capture(), this writes compressed sections directly: no raw world copy on disk
-- and no later compression job on match exit or replay startup.
function M.writeSnapshot(filename,engine)
  assert(engine:networkState().syncStatus==0,'Cannot snapshot a synchronizing world')
  local tick=engine:tick()
  local entries=M.layout()
  local header,descriptor=require('code/world-header').read()
  local _,_,extensions=M.extensionState()
  local reader={entries=entries,header=header,manifest={header=descriptor},extensions=extensions}
  function reader:eachSection(consume)
    for _,entry in ipairs(self.entries) do
      local data=core.readString(entry.address,entry.size)
      assert(type(data)=='string' and #data==entry.size,'Short native world read')
      consume(entry,data)
    end
  end
  -- No progress callback: yielding would allow a different world between sections.
  local result=require('code/world-container').write(filename,reader)
  assert(engine:tick()==tick,'Simulation advanced during world capture')
  return result
end
return M
