-- Read/verify only. No native world, playback flag or presentation state changes
-- until the session consumes the completed result. Progress may yield to the UI.
local store=require('code/sessions')
local native=require('code/native')
local digest=require('code/native-hash')
local M={}
function M.prepare(id,engine,worlds,progress)
  if progress then progress('Checking replay data...') end
  local manifest=store.load(id,native.profile)
  assert(store.compatible(manifest),'Replay requires its recorded UCP settings')
  -- The MP chain owns validation for every segment, including the first one.
  if not manifest.multiplayer or worlds then store.preflight(manifest,progress) end
  local path=store.path(id)
  local environment=json:decode(store.read(path..'/environment.json'))
  if type(environment)=='table' and environment.assets then
    require('code/replay-assets').verify(environment.assets,progress)
  end
  if progress then progress('Checking starting state...') end
  local snapshotPath,snapshotHash=path..'/start.sav',manifest.snapshotHash
  if manifest.multiplayer then
    worlds=worlds or require('code/multiplayer-session').prepareChain(manifest,engine,progress)
    local world=assert(worlds[id],'Recovery world was not prepared')
    snapshotPath,snapshotHash=world.path,world.hash
  end
  local hash=digest.file(snapshotPath,1024*1024*1024,nil,progress and function()
    progress('Checking starting state...')
  end)
  assert(hash==snapshotHash,'Starting save is damaged')
  local rng=store.read(path..'/rng.bin')
  assert(#rng==0x9c50 and digest.sha256(rng)==manifest.rngHash,'Starting RNG state is damaged')
  return {manifest=manifest,snapshotPath=snapshotPath,snapshotHash=snapshotHash,rng=rng,worlds=worlds,info=environment.display}
end

-- A seek can happen long after initial preparation. Check the starting file
-- again before releasing the active world; prepared metadata is not a file lock.
function M.checkStartingState(ready)
  local expected=ready.snapshotHash or ready.manifest.snapshotHash
  assert(digest.file(ready.snapshotPath,1024*1024*1024)==expected,'Starting save is damaged')
  assert(#ready.rng==0x9c50 and digest.sha256(ready.rng)==ready.manifest.rngHash,
    'Starting RNG state is damaged')
end
return M
