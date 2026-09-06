local platform = require('code/platform')
local validation = require('code/validation')
local M = {FORMAT = 1, ROOT = 'ucp/replays', PROFILE = 'recorder-sp-v10'}
local activeSettings

local function read(path)
  local f, err = io.open(path, 'rb')
  assert(f, tostring(err))
  local data = assert(f:read('*a'))
  assert(f:close())
  return data
end

local function write(path, data)
  local f, err = io.open(path, 'wb')
  assert(f, tostring(err))
  local ok, reason = f:write(data)
  local closed, closeReason = f:close()
  assert(ok and closed, tostring(reason or closeReason))
end

function M.path(id)
  assert(type(id) == 'string' and #id < 80 and id:match('^[%w_-]+$'), 'Invalid replay identifier')
  return M.ROOT .. '/' .. id
end

-- Stable encoding: Lua table iteration order is not a compatibility boundary.
local function canonical(value)
  if type(value)~='table' then return json:encode(value) end
  local keys={}; for key in pairs(value) do keys[#keys+1]=key end
  table.sort(keys,function(a,b) return tostring(a)<tostring(b) end)
  local entries={}
  for _,key in ipairs(keys) do entries[#entries+1]=json:encode(tostring(key))..':'..canonical(value[key]) end
  return '{'..table.concat(entries,',')..'}'
end

function M.captureSettings()
  local restartSettings,resolved=require('code/recorded-settings').capture(allActiveExtensions,configFinal)
  local extensions={}
  for i,extension in ipairs(allActiveExtensions or {}) do
    extensions[i]={name=extension.name,version=extension.version}
  end
  local raw=read(CONFIG_FILE)
  local environment=canonical({extensions=extensions,config=resolved,
    framework=read('ucp/ucp-version.yml')})
  activeSettings={raw=raw,hash=sha.sha256(raw),environment=environment,environmentHash=sha.sha256(environment),
    settingsCapture='resolved-v1',restartSettings=restartSettings,restartSettingsHash=sha.sha256(restartSettings)}
end

function M.settings()
  if activeSettings then return activeSettings end
  local raw = read(CONFIG_FILE)
  return {raw=raw,hash=sha.sha256(raw),environment='{}',environmentHash=sha.sha256('{}')}
end

function M.new(profile)
  platform.mkdir(M.ROOT)
  local prefix = os.date('!%Y%m%d-%H%M%S')
  local removed={}
  local ok,entries=pcall(function() return ucp.internal.io.directories(M.ROOT..'/removed') or {} end)
  if ok then
    for _,entry in ipairs(entries) do
      local old=entry:gsub('[/\\]+$',''):match('([^/\\]+)$')
      if old then removed[old]=true end
    end
  end
  local id, path
  for i=1,9999 do
    id=prefix .. '-' .. string.format('%04d', i)
    path=M.path(id)
    if not removed[id] and platform.mkdir(path) then break end
    assert(i < 9999, 'Cannot allocate replay name')
  end
  local settings=M.settings()
  write(path .. '/ucp-config.yml', settings.raw)
  write(path .. '/environment.json',settings.environment)
  if settings.restartSettings then write(path..'/replay-config.yml',settings.restartSettings) end
  local manifest={format=M.FORMAT, id=id, variant=profile.name,
    executable=profile.sha256, simulationProfile=M.PROFILE,
    settingsHash=settings.hash,environmentHash=settings.environmentHash,settingsCapture=settings.settingsCapture,
    restartSettingsHash=settings.restartSettingsHash,created=os.date('!%Y-%m-%dT%H:%M:%SZ'),
    status='armed', commandCount=0, lastTick=0}
  M.save(manifest)
  return manifest
end

function M.save(manifest)
  local path=M.path(manifest.id) .. '/manifest.json'
  write(path .. '.tmp', json:encode(manifest))
  platform.replace(path .. '.tmp', path)
end

-- Display names are metadata, never paths. Duplicate names cannot overwrite replays.
function M.rename(id,name,profile)
  name=validation.displayName(name)
  local manifest=M.load(id,profile)
  manifest.displayName=name
  M.save(manifest)
  return manifest
end

function M.title(manifest)
  local ok,name=pcall(validation.displayName,manifest.displayName)
  return ok and name or manifest.id
end

function M.remove(id)
  -- Do not require a playable profile: incomplete and old captures also need
  -- library management. Check identity and state before moving the whole folder.
  local manifest=json:decode(read(M.path(id)..'/manifest.json'))
  assert(type(manifest)=='table' and manifest.id==id,'Replay identity differs')
  assert(manifest.status~='recording' and manifest.status~='copying',
    'An active recording cannot be removed')
  platform.removeReplay(M.ROOT,id)
end

-- Seal a separate copy at the last observed boundary without stopping capture or
-- calling the native save routine again. The source streams remain untouched.
function M.copy(source,name,finalRngHash)
  name=validation.displayName(name)
  local copy=M.new({name=source.variant,sha256=source.executable})
  local id,created=copy.id,copy.created
  for key,value in pairs(source) do copy[key]=value end
  copy.settingsCapture=source.settingsCapture; copy.restartSettingsHash=source.restartSettingsHash
  copy.id=id; copy.created=created; copy.displayName=name; copy.sourceId=source.id
  copy.status='copying'; copy.finalRngHash=finalRngHash
  local path,original=M.path(id),M.path(source.id)
  local ok,reason=xpcall(function()
    M.save(copy)
    for _,file in ipairs({'start.sav','rng.bin','ucp-config.yml','environment.json',
      'stream-commands.json','stream-rng-sync.json','stream-infself.json'}) do
      write(path..'/'..file,read(original..'/'..file))
    end
    assert(sha.sha256(read(path..'/start.sav'))==copy.snapshotHash,'Starting save is damaged')
    assert(sha.sha256(read(path..'/rng.bin'))==copy.rngHash,'Starting RNG state is damaged')
    assert(sha.sha256(read(path..'/ucp-config.yml'))==copy.settingsHash,'Recorded settings are damaged')
    assert(sha.sha256(read(path..'/environment.json'))==copy.environmentHash,'Recorded environment is damaged')
    if copy.restartSettingsHash then
      write(path..'/replay-config.yml',read(original..'/replay-config.yml'))
      assert(sha.sha256(read(path..'/replay-config.yml'))==copy.restartSettingsHash,'Recorded launch settings are damaged')
    end
    M.finish(copy)
  end,debug.traceback)
  if not ok then copy.status='failed'; pcall(M.save,copy); error(reason) end
  return copy
end

function M.list()
  local entries=ucp.internal.io.directories(M.ROOT) or {}
  local result={}
  for _, entry in ipairs(entries) do
    local id=entry:gsub('[/\\]+$', ''):match('([^/\\]+)$')
    local ok, manifest=pcall(function() return json:decode(read(M.path(id)..'/manifest.json')) end)
    if ok and type(manifest)=='table' and manifest.id==id then result[#result+1]=manifest end
  end
  table.sort(result, function(a,b) return a.id>b.id end)
  return result
end

function M.load(id, profile)
  local manifest=json:decode(read(M.path(id) .. '/manifest.json'))
  assert(type(manifest)=='table' and manifest.format==M.FORMAT and manifest.id==id, 'Unsupported replay format')
  assert(manifest.variant==profile.name and manifest.executable==profile.sha256, 'Replay requires ' .. tostring(manifest.variant))
  assert(manifest.simulationProfile==M.PROFILE, 'Replay uses a different simulation profile')
  assert(manifest.status=='complete', 'Recording was not completed')
  validation.manifest(manifest)
  assert(sha.sha256(read(M.path(id)..'/ucp-config.yml'))==manifest.settingsHash, 'Recorded settings are damaged')
  assert(sha.sha256(read(M.path(id)..'/environment.json'))==manifest.environmentHash,'Recorded environment is damaged')
  if manifest.restartSettingsHash then
    assert(sha.sha256(read(M.path(id)..'/replay-config.yml'))==manifest.restartSettingsHash,'Recorded launch settings are damaged')
  end
  return manifest
end

local streams={commands='stream-commands.json',checkpoints='stream-rng-sync.json',info='stream-infself.json'}

-- Seal only commands that fall within the last observed simulation boundary.
-- Inputs queued for a later tick when the player leaves are not part of this replay.
function M.finish(manifest)
  local path=M.path(manifest.id)
  local commandsPath=path..'/'..streams.commands
  local input=assert(io.open(commandsPath,'rb'))
  local output, openError=io.open(commandsPath..'.tmp','wb')
  if not output then input:close(); error(openError) end
  local count, previous=0,manifest.startTick
  local ok,reason=xpcall(function()
    for line in input:lines() do
      local c=validation.sessionCommand(json:decode(line),manifest)
      assert(c.time>=previous,'Replay commands are out of order')
      previous=c.time
      if c.time<=manifest.lastTick then
        assert(output:write(line..'\n')); count=count+1
      end
    end
  end,debug.traceback)
  local inClosed=input:close(); local outClosed=output:close()
  assert(ok and inClosed and outClosed,reason or 'Cannot finish replay command stream')
  platform.replace(commandsPath..'.tmp',commandsPath)
  manifest.commandCount=count
  for name,file in pairs(streams) do manifest[name..'Hash']=sha.sha256(read(path..'/'..file)) end
  M.preflight(manifest)
  manifest.status='complete'
  M.save(manifest)
end

-- Check every stream before loading the native save, including data near EOF.
function M.preflight(manifest)
  validation.manifest(manifest)
  local path=M.path(manifest.id)
  local data={}
  for name,file in pairs(streams) do
    data[name]=read(path..'/'..file)
    assert(sha.sha256(data[name])==manifest[name..'Hash'],'Replay '..name..' stream is damaged')
  end
  local count,previous,batchSize=0,manifest.startTick,0
  for line in data.commands:gmatch('[^\r\n]+') do
    local c=validation.sessionCommand(json:decode(line),manifest)
    assert(c.time>=previous and c.time<=manifest.lastTick,'Replay command tick is outside its ordered timeline')
    batchSize=c.time==previous and batchSize+1 or 1
    assert(batchSize<=100,'Replay exceeds the native 100-command dispatch batch')
    count=count+1; previous=c.time
  end
  assert(count==manifest.commandCount,'Replay command count differs')
  local tick=math.ceil(manifest.startTick/64)*64
  for line in data.checkpoints:gmatch('[^\r\n]+') do
    local checkpoint=json:decode(line)
    assert(type(checkpoint)=='table' and checkpoint.time==tick and tick<=manifest.lastTick,'Invalid replay checkpoint timeline')
    validation.rng(checkpoint.rng)
    validation.resources(checkpoint.resources)
    validation.hash(checkpoint.rngHash,'checkpoint RNG hash')
    tick=tick+64
  end
  assert(tick>manifest.lastTick,'Replay verification data ended early')
  validation.info(json:decode(data.info))
end

function M.compatible(manifest)
  local current=M.settings()
  return (manifest.settingsCapture=='resolved-v1' or current.hash==manifest.settingsHash)
    and current.environmentHash==manifest.environmentHash
    and require('code/automarket-replay').compatible(manifest.automarket)
end

M.read, M.write = read, write
return M
