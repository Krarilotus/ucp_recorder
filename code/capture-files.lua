local store=require('code/sessions')
local platform=require('code/platform')
local validation=require('code/validation')
local native=require('code/native')
local M={}

function M.save(capture)
  store.write(capture.path..'/capture.json.tmp',json:encode(capture))
  platform.replace(capture.path..'/capture.json.tmp',capture.path..'/capture.json')
end

function M.begin(path,engine,settings)
  local capture={format=1,kind='multiplayer-capture',id=path:match('([^/]+)$'),path=path,
    status='recording',playable=false,created=os.date('!%Y-%m-%dT%H:%M:%SZ'),
    variant=native.profile.name,executable=native.profile.sha256,startTick=engine:tick(),
    initialNetwork=engine:networkState(),settingsHash=settings.hash,
    environmentHash=settings.environmentHash,restartSettingsHash=settings.restartSettingsHash,
    missing={'initial-world-snapshot','offline-network-identity','immediate-and-system-playback','resynchronization-restoration'}}
  -- Commit a non-playable manifest first; interrupted setup remains identifiable.
  M.save(capture)
  store.write(path..'/ucp-config.yml',settings.raw)
  store.write(path..'/environment.json',settings.environment)
  if settings.restartSettings then store.write(path..'/replay-config.yml',settings.restartSettings) end
  local rng=engine:rngData()
  store.write(path..'/initial-rng.bin',rng)
  capture.rngHash=sha.sha256(rng)
  capture.initialResources=engine:resourceState()
  -- World evidence is independent of command persistence: an unsupported
  -- layout or failed world write must not discard the useful command journal.
  local ok,world=pcall(require('code/world-capture').capture,path,engine)
  capture.world=ok and world or {status='failed',reason=tostring(world)}
  if ok then
    capture.missing[1]='native-world-restore-and-extension-state-coverage'
  end
  M.save(capture)
  return capture
end

-- Copy exactly the flushed byte prefix. Never stop or edit the source stream.
local function prefix(source,target,size)
  local input=assert(io.open(source,'rb'))
  local output,err=io.open(target,'wb')
  if not output then input:close(); error(err) end
  local ok,reason=pcall(function()
    local remaining=size or assert(input:seek('end'))
    assert(input:seek('set',0))
    while remaining>0 do
      local chunk=assert(input:read(math.min(remaining,65536)),'Capture prefix ended early')
      assert(#chunk>0 and #chunk<=remaining,'Invalid capture prefix')
      assert(output:write(chunk)); remaining=remaining-#chunk
    end
  end)
  local a,b=input:close(),output:close()
  assert(ok and a and b,reason or 'Cannot close capture copy')
end

function M.copy(source,name,bytes,events,commands,tick)
  name=validation.displayName(name)
  local path
  for i=1,9999 do
    local candidate=source.path..'-copy-'..string.format('%04d',i)
    if platform.mkdir(candidate) then path=candidate; break end
  end
  assert(path,'Cannot allocate capture copy')
  local copy={}
  for k,v in pairs(source) do copy[k]=v end
  copy.id=path:match('([^/]+)$'); copy.path=path; copy.sourceId=source.id
  copy.displayName=name; copy.created=os.date('!%Y-%m-%dT%H:%M:%SZ'); copy.status='copying'
  copy.bytes=bytes; copy.events=events; copy.commands=commands; copy.lastObservedTick=tick
  M.save(copy)
  local ok,err=pcall(function()
    for _,file in ipairs({'ucp-config.yml','environment.json','initial-rng.bin'}) do
      prefix(source.path..'/'..file,path..'/'..file)
    end
    if source.restartSettingsHash then prefix(source.path..'/replay-config.yml',path..'/replay-config.yml') end
    if source.world and source.world.status=='complete' then
      prefix(source.path..'/world.json',path..'/world.json')
      prefix(source.path..'/world-layout.bin',path..'/world-layout.bin')
      prefix(source.path..'/world.bin',path..'/world.bin')
      if source.world.header then prefix(source.path..'/world-header.bin',path..'/world-header.bin') end
      if source.world.automarket then prefix(source.path..'/automarket.bin',path..'/automarket.bin') end
    end
    prefix(source.path..'/commands.jsonl',path..'/commands.jsonl',bytes)
    copy.status='snapshot'; M.save(copy)
  end)
  if not ok then copy.status='interrupted'; pcall(M.save,copy); error(err) end
  return copy
end
return M
