-- Convert durable peer observations into the shared local replay format. Native
-- world construction stays in world-container; scheduling stays in the engine.
local store=require('code/sessions')
local validation=require('code/validation')
local ticks=require('code/tick-journal')
local M={PROFILE='recorder-mp-v1',MAX_TICKS=128*1024*1024}

function M.presentationOrTransport(event)
  if event.reason~='immediate command is outside timed replay coverage' then return false end
  local packet=event.details
  if type(packet)~='table' or packet.scheduledTime~=0 then return false end
  local size=packet.category==12 and 10 or packet.category==117 and 136
  return size and packet.size==size and type(packet.data)=='string'
    and #packet.data==size*2 and not packet.data:find('[^%x]')
end

function M.seal(capture)
  local path=capture.path
  local manifest={format=store.FORMAT,id=capture.id,variant=capture.variant,executable=capture.executable,
    simulationProfile=M.PROFILE,multiplayer=capture.initialNetwork,created=capture.created,savedAt=capture.savedAt,
    displayName=capture.displayName,sourceId=capture.sourceId,status='failed',battle=capture.battle,
    nextReplay=capture.nextReplay,previousReplay=capture.previousReplay,
    settingsHash=capture.settingsHash,environmentHash=capture.environmentHash,
    settingsCapture=capture.settingsCapture,restartSettingsHash=capture.restartSettingsHash,
    automarket=capture.automarket,player=capture.initialNetwork.localPlayer,
    startTick=capture.startTick,lastTick=capture.lastObservedTick,
    startResources=capture.initialResources,finalResources=capture.finalResources,
    finalRng=capture.finalRng,finalRngHash=capture.finalRngHash,rngHash=capture.rngHash,
    snapshotHash=capture.world and capture.world.hash,commandCount=0}
  local opened={}
  local ok,reason=xpcall(function()
    assert(capture.status=='closed' or capture.status=='snapshot','Multiplayer capture was interrupted')
    assert(capture.tickProfile=='native-tick-rng-v1','Record a new match with simulation boundary capture')
    assert(capture.world and capture.world.status=='complete' and capture.world.header,
      'Multiplayer starting world is unavailable')
    require('code/offline-runtime').roster(manifest.multiplayer)
    local rng=store.read(path..'/initial-rng.bin')
    assert(#rng==0x9c50 and sha.sha256(rng)==manifest.rngHash,'Starting RNG state is damaged')
    store.write(path..'/rng.bin',rng)
    local function word(i)
      local a,b,c,d=rng:byte(i,i+3); local value=a+b*256+c*65536+d*16777216
      return value>=2147483648 and value-4294967296 or value
    end
    local initial=ticks.values(rng:sub(1,4)..rng:sub(0x9c49,0x9c50))
    store.write(path..'/stream-infself.json',json:encode({gameType=0,mapSeed=word(5),matchSeed=word(5),
      RNGvalue1=initial[1],RNGvalue2=initial[2],RNGindex1=initial[4],RNGindex2=initial[3]}))
    local function open(file,mode)
      local f=assert(io.open(path..'/'..file,mode)); opened[#opened+1]=f; return f
    end
    local commands=open('stream-commands.json','wb')
    local checkpoints=open('stream-rng-sync.json','wb')
    local journal=open('commands.jsonl','rb')
    assert(journal:seek('end')==capture.bytes,'Multiplayer journal length differs')
    assert(journal:seek('set',0))
    local sequence,previous,commandCount=0,manifest.startTick,0
    local header,footer
    for line in journal:lines() do
      local event=json:decode(line)
      assert(type(event)=='table' and not footer,'Invalid multiplayer journal event after ending')
      if event.sequence then
        assert(header,'Multiplayer journal header is missing')
        sequence=sequence+1; assert(event.sequence==sequence,'Multiplayer journal sequence differs')
        validation.integer(event.time,0,2147483647,'journal tick')
        if event.kind=='command' then commandCount=commandCount+1 end
        if not capture.replayEvents or sequence<=capture.replayEvents then
          assert(event.time>=previous,'Multiplayer world restoration requires a recovery segment')
          previous=event.time
        if event.kind=='command' and event.time<=manifest.lastTick then
          local command={time=event.time,commandCategory=event.category,player=event.player,
            size=event.size,data=event.data,beforeRng=event.beforeRng,afterRng=event.rng}
          validation.sessionCommand(command,manifest)
          assert(commands:write(json:encode(command)..'\n'))
          manifest.commandCount=manifest.commandCount+1
        elseif event.kind=='checkpoint' and event.time<=manifest.lastTick then
          assert(checkpoints:write(json:encode({time=event.time,rng=event.rng,rngHash=event.rngHash,
            resources=event.resources})..'\n'))
        elseif event.kind=='gap' then
          assert(M.presentationOrTransport(event),'Uncovered multiplayer event: '..tostring(event.reason))
        else assert(event.kind=='command','Untracked multiplayer command or event') end
        end
      elseif event.kind=='header' then
        assert(not header and sequence==0 and event.format==5
          and event.variant==manifest.variant and event.executable==manifest.executable
          and event.environmentHash==manifest.environmentHash and event.firstTick==manifest.startTick
          and event.localPlayer==manifest.player,'Multiplayer journal identity differs')
        header=true
      elseif event.kind=='end' then
        assert(header and event.events==sequence and event.commands==commandCount,
          'Multiplayer journal ending counts differ')
        footer=true
      else error('Unframed multiplayer event') end
    end
    assert(header and (footer or capture.status=='snapshot'),'Multiplayer journal was not sealed')
    assert(sequence==capture.events and commandCount==capture.commands,'Multiplayer capture counts differ')
    if capture.replayEvents then validation.integer(capture.replayEvents,0,sequence,'recovery boundary') end
  end,debug.traceback)
  for _,file in ipairs(opened) do
    local closed,closeError=file:close()
    if not closed then ok=false; reason=reason or closeError end
  end
  if ok then
    ok,reason=xpcall(function()
      manifest.ticksHash=require('code/native-hash').file(path..'/ticks.bin',M.MAX_TICKS)
      for name,file in pairs({commands='commands',checkpoints='rng-sync',info='infself'}) do
        manifest[name..'Hash']=sha.sha256(store.read(path..'/stream-'..file..'.json'))
      end
      store.preflight(manifest)
      manifest.status='complete'
    end,debug.traceback)
  end
  if not ok then manifest.reason=tostring(reason):match('^[^\n]+'):gsub('^.-:%d+: ','') end
  store.write(path..'/manifest.json.tmp',json:encode(manifest))
  require('code/platform').replace(path..'/manifest.json.tmp',path..'/manifest.json')
  return manifest
end

function M.preflight(manifest,path)
  require('code/offline-runtime').roster(manifest.multiplayer)
  if manifest.nextReplay then store.path(manifest.nextReplay) end
  validation.hash(manifest.ticksHash,'tick journal hash')
  assert(require('code/native-hash').file(path..'/ticks.bin',M.MAX_TICKS)==manifest.ticksHash,
    'Recorded simulation ticks are damaged')
  local file=assert(io.open(path..'/ticks.bin','rb'))
  local ok,reason=pcall(function()
    local expected=manifest.startTick
    while true do
      local raw=file:read(ticks.SIZE)
      if not raw then break end
      local frame=ticks.decode(raw)
      assert(frame.time==expected,'Recorded simulation ticks are not continuous')
      expected=expected+1
    end
    assert(expected>=manifest.lastTick and expected<=manifest.lastTick+1,
      'Recorded simulation ticks ended early or passed the ending boundary')
  end)
  local closed=file:close(); assert(ok and closed,reason or 'Cannot close tick journal')
end

function M.prepare(manifest,engine)
  local path=store.path(manifest.id)
  local result=require('code/world-container').prepare(path,engine)
  assert(result.sourceWorldHash==manifest.snapshotHash,'Starting multiplayer world changed')
  return path..'/world-native.sav',result.sha256
end

-- Prepare the entire recovery chain while still in the single-player browser.
-- Missing settings/assets or a broken link must fail before the first world load.
function M.prepareChain(first,engine)
  local prepared,manifest={},first
  for _=1,32 do
    assert(not prepared[manifest.id],'Replay recovery chain contains a cycle')
    assert(manifest.simulationProfile==M.PROFILE and manifest.environmentHash==first.environmentHash
      and manifest.executable==first.executable,'Recovery segment requires a different environment')
    store.preflight(manifest)
    local path,hash=M.prepare(manifest,engine)
    prepared[manifest.id]={path=path,hash=hash}
    if not manifest.nextReplay then return prepared end
    local loaded,nextManifest=pcall(store.load,manifest.nextReplay,require('code/native').profile)
    if not loaded then
      prepared.incomplete={after=manifest.id,reason=tostring(nextManifest)}
      return prepared
    end
    assert(nextManifest.previousReplay==manifest.id,'Replay recovery link differs')
    manifest=nextManifest
  end
  error('Replay has more than 32 recovery segments')
end
return M
