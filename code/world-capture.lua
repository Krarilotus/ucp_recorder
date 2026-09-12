-- Read native save sections; never call the native multiplayer save routine.
local native=require('code/native')
local sections=require('code/world-sections')
local store=require('code/sessions')
local digest=require('code/native-hash')
local M={CHUNK=65536}

function M.layout()
  local schema=assert(sections[native.profile.name],'Unsupported world capture executable')
  local owner=require('code/native-save').interface()
  local raw=core.readString(owner.sections,schema.bytes)
  local entries,profile=require('code/world-layout').decode(raw,native.profile.name)
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
  local requiredState=require('code/required-state').capture(custom)
  if next(custom) then
    local raw=require('code/extension-container').encode(custom)
    extensionData=raw
    extensionInfo={bytes=#raw,sha256=sha.sha256(raw),ucp2=legacy~=nil,requiredState=requiredState}
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
-- Freeze once on the simulation thread; compression only sees private memory.
-- This is the same checked section/header/extension source used by MP capture.
function M.freeze(engine)
  assert(not engine.executing and not engine:commandsPending(),'Snapshot requires an idle command boundary')
  local entries,profile=M.layout()
  local header,descriptor=require('code/world-header').read()
  local _,_,extensions=M.extensionState()
  local bytes=profile.total+(extensions and #extensions or 0)
  assert(bytes<=require('code/codec-worker').MAX_BYTES,'Frozen world exceeds memory budget')
  local memory=core.allocate(bytes+1,true) -- a binary bridge may append a trailing NUL
  assert(memory and memory~=0,'Cannot allocate frozen world')
  local reader={entries=entries,header=header,manifest={header=descriptor},extensions=extensions,
    precompressed=true,memory=memory}
  local ok,reason=pcall(function()
    local inputs,offset={},0
    for _,entry in ipairs(entries) do
      core.copyMemory(memory+offset,entry.address,entry.size)
      inputs[#inputs+1]={address=memory+offset,size=entry.size,compress=entry.compressed~=0}
      offset=offset+entry.size
    end
    if extensions then
      require('code/binary-memory').write(memory+offset,extensions)
      inputs[#inputs+1]={address=memory+offset,size=#extensions,compress=true}
    end
    reader.inputs=inputs
    reader.worker=require('code/codec-worker').new(inputs,require('code/world-codec').compressorAddress())
  end)
  if not ok then core.deallocate(memory); error(reason) end
  function reader:ready() return self.worker:ready() end
  function reader:cancel() self.worker:cancel() end
  function reader:eachSection(consume)
    for i,entry in ipairs(self.entries) do
      local packed=self.worker:packed(i)
      local raw=not packed and core.readString(self.inputs[i].address,entry.size) or nil
      consume(entry,raw,packed)
    end
  end
  function reader:write(filename)
    assert(self:ready(),'Snapshot compression is still running')
    if self.extensions then self.packedExtensions=self.worker:packed(#self.inputs) end
    return require('code/world-container').write(filename,self)
  end
  function reader:close()
    self.worker:close(); core.deallocate(self.memory); self.memory=nil
  end
  return reader
end
return M
