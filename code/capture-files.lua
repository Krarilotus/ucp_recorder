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
    settingsCapture=settings.settingsCapture,automarket=require('code/automarket-replay').current(),
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

local prefix=require('code/replay-files').copy

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
  copy.previousReplay=nil; copy.nextReplay=nil
  copy.bytes=bytes; copy.events=events; copy.commands=commands; copy.lastObservedTick=tick
  M.save(copy)
  local ok,err=pcall(function()
    if source.battle then prefix(source.path..'/battle.bin',path..'/battle.bin') end
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
      if source.world.extensions then prefix(source.path..'/extensions.zip',path..'/extensions.zip') end
    end
    prefix(source.path..'/commands.jsonl',path..'/commands.jsonl',bytes)
    if source.tickProfile then prefix(source.path..'/ticks.bin',path..'/ticks.bin',source.tickBytes) end
    copy.status='snapshot'; M.save(copy)
  end)
  if not ok then copy.status='interrupted'; pcall(M.save,copy); error(err) end
  return copy
end

function M.seal(capture)
  local replay=require('code/multiplayer-session').seal(capture)
  capture.replayStatus=replay.status; capture.replayReason=replay.reason
  capture.playable=replay.status=='complete'
  capture.missing=capture.playable and {} or {replay.reason}
  M.save(capture)
  return replay
end

-- A named prefix owns copies of every earlier recovery world, so removing the
-- automatic source later cannot break the named recording halfway through.
function M.copyChain(source,name,bytes,events,commands,tick)
  local originals={source}; local seen={[source.id]=true}
  local current=source
  while current.previousReplay do
    assert(#originals<32 and not seen[current.previousReplay],'Invalid replay recovery chain')
    seen[current.previousReplay]=true
    local previous=json:decode(store.read(store.path(current.previousReplay)..'/capture.json'))
    assert(previous.id==current.previousReplay and previous.nextReplay==current.id
      and previous.status=='closed','Previous recovery segment is unavailable')
    originals[#originals+1]=previous; current=previous
  end
  local copies={}
  for i=#originals,1,-1 do
    local original=originals[i]
    local copy=M.copy(original,name,i==1 and bytes or original.bytes,
      i==1 and events or original.events,i==1 and commands or original.commands,
      i==1 and tick or original.lastObservedTick)
    local previous=copies[#copies]
    if previous then previous.nextReplay=copy.id; copy.previousReplay=previous.id end
    copies[#copies+1]=copy
  end
  for _,copy in ipairs(copies) do
    M.seal(copy)
  end
  return copies[1]
end
return M
