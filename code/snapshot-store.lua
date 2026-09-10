-- Restorable worlds use the game's compressed save format and loader. This
-- owner publishes optional files atomically; it never schedules simulation work.
local store=require('code/sessions')
local digest=require('code/native-hash')
local platform=require('code/platform')
local validation=require('code/validation')
local M={PROFILE='native-before-clock-v1',MAX_WORLD=7*1024*1024,MAX_POINTS=512}

local function world(path) return path..'.sav' end
local function rng(path) return path..'.rng' end

function M.validate(point,manifest)
  assert(type(point)=='table' and point.profile==M.PROFILE,'Unsupported restore point')
  validation.integer(point.tick,manifest.startTick,manifest.lastTick,'snapshot tick')
  validation.integer(point.month,-1200000,1200011,'snapshot calendar')
  validation.integer(point.commands,0,manifest.commandCount,'snapshot command count')
  validation.integer(point.bytes,1001,M.MAX_WORLD,'snapshot size')
  validation.hash(point.worldHash,'snapshot world hash')
  validation.hash(point.rngHash,'snapshot RNG hash')
  validation.hash(point.stateHash,'snapshot state hash')
  require('code/replay-streams').validateBookmark(point.bookmark,{commandsFile=true,rngFile=true,infoFile=true,
    tickFile=manifest.multiplayer and true or nil,phaseFile=manifest.phaseProfile and true or nil})
  if point.bookmark.nextCommand then validation.sessionCommand(point.bookmark.nextCommand,manifest) end
  if point.bookmark.nextWork then require('code/maintenance-journal').validate(point.bookmark.nextWork,manifest) end
  assert(point.bookmark.workEnded==nil or type(point.bookmark.workEnded)=='boolean','Invalid snapshot EOF state')
  return point
end

function M.path(manifest,point)
  validation.integer(point.tick,manifest.startTick,manifest.lastTick,'snapshot tick')
  return store.path(manifest.id)..'/snapshots/'..point.tick
end

function M.cachePath()
  return require('code/snapshot-cache').allocate()
end

function M.remove(path)
  -- Only exact paths retained by the cache owner are removed, never enumeration
  -- of a replay folder or recursive deletion of user-supplied content.
  local failed
  for _,file in ipairs({world(path),rng(path)}) do
    local removed,reason,code=os.remove(file)
    if not removed and code~=2 then failed=failed or reason end -- ENOENT is already removed.
  end
  return not failed,failed
end

function M.capture(session,path,month)
  local engine=session.engine
  assert(not engine.executing and not engine:commandsPending() and not session.pendingTick,
    'Restore point requires an idle command/tick boundary')
  local tick=engine:tick()
  local started=platform.milliseconds()
  local random,resources=engine:rngData(),engine:resourceData()
  local point={profile=M.PROFILE,tick=tick,month=month,
    commands=session.mode=='record' and session.manifest.commandCount or session.playedCommands,
    bookmark=session:bookmark(),rngHash=digest.sha256(random),stateHash=digest.sha256(random..resources)}
  local ok,reason=xpcall(function()
    engine:saveSnapshot(world(path)..'.tmp')
    point.saveMilliseconds=(platform.milliseconds()-started)%4294967296
    point.bytes=0
    point.worldHash=digest.file(world(path)..'.tmp',M.MAX_WORLD,nil,function(count) point.bytes=count end)
    store.write(rng(path)..'.tmp',random)
    assert(engine:tick()==tick and engine:rngData()==random and engine:resourceData()==resources,
      'Snapshot capture changed simulation state')
    platform.replace(world(path)..'.tmp',world(path))
    platform.replace(rng(path)..'.tmp',rng(path))
  end,debug.traceback)
  if not ok then os.remove(world(path)..'.tmp'); os.remove(rng(path)..'.tmp'); M.remove(path) end
  -- A disk/cache failure is optional. A changed world cannot be ignored.
  assert(engine:tick()==tick and engine:rngData()==random and engine:resourceData()==resources,
    'Snapshot capture changed simulation state')
  if not ok then return nil,reason end
  print(string.format('[recorder] Snapshot at tick %d: %d bytes; native save %d ms; total %d ms',
    tick,point.bytes,point.saveMilliseconds,(platform.milliseconds()-started)%4294967296))
  point.saveMilliseconds=nil -- Timing is diagnostic output, not saved replay state.
  return point
end

function M.prepare(manifest,point,path)
  M.validate(point,manifest)
  local base=store.path(manifest.id)
  local paths={commandsFile='/stream-commands.json',rngFile='/stream-rng-sync.json',infoFile='/stream-infself.json',
    tickFile='/ticks.bin',phaseFile='/'..require('code/maintenance-journal').FILE}
  for field,offset in pairs(point.bookmark.positions) do
    local file=assert(io.open(base..paths[field],'rb'),'Snapshot source stream is unavailable')
    local bytes=file:seek('end'); local closed=file:close()
    assert(bytes and closed and offset<=bytes,'Snapshot stream position is outside its source')
  end
  local size=0
  local hash=digest.file(world(path),M.MAX_WORLD,nil,function(count) size=count end)
  assert(hash==point.worldHash and size==point.bytes,'Cached world is damaged')
  local file=assert(io.open(rng(path),'rb'),'Cached RNG state is missing')
  local random=file:read(0x9c51)
  local closed=file:close()
  assert(closed and type(random)=='string','Cannot read cached RNG state')
  assert(#random==0x9c50 and digest.sha256(random)==point.rngHash,'Cached RNG state is damaged')
  return {point=point,snapshotPath=world(path),rng=random}
end

function M.copy(source,target)
  target.snapshots={}
  for _,point in ipairs(source.snapshots or {}) do
    local to
    local ok,reason=pcall(function()
      M.validate(point,source)
      if point.tick>target.lastTick then return end
      platform.mkdir(store.path(target.id)..'/snapshots')
      local from=M.path(source,point); to=M.path(target,point)
      M.prepare(source,point,from)
      require('code/replay-files').copy(world(from),world(to),point.bytes)
      require('code/replay-files').copy(rng(from),rng(to),0x9c50)
      target.snapshots[#target.snapshots+1]=point
    end)
    if not ok then
      if to then M.remove(to) end
      print('[recorder] Optional restore point omitted from named copy: '..tostring(reason))
    end
  end
  if #target.snapshots==0 then target.snapshots=nil end
end

return M
