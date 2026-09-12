-- A replay has native human slots but no live transport. The original command
-- translator and simulation keep their recorded multiplayer mode. Only the
-- transport/pacing owners see offline behaviour; no temporary global mode swaps
-- occur during ticks or command execution.
local validation=require('code/validation')
local M={}

---@class OfflineRoster
---@field mode integer Recorded native multiplayer mode.
---@field localPlayer integer Recorded spectator's original human slot.
---@field handles integer[] Synthetic handles indexed by native player slot.
---@field roster table[] Original human/AI/empty identities.
---@param state table Captured network identity, not a native pointer-bearing packet.
---@return OfflineRoster
function M.roster(state)
  assert(type(state)=='table' and (state.mode==1 or state.mode==2),'Unsupported recorded multiplayer mode')
  assert(state.syncStatus==0,'Starting world was captured during synchronization')
  validation.integer(state.localPlayer,1,8,'recorded local player')
  assert(type(state.handles)=='table' and #state.handles==8
    and type(state.roster)=='table' and #state.roster==8,'Incomplete recorded player roster')
  local result={mode=state.mode,localPlayer=state.localPlayer,handles={},roster={}}
  local seen={}
  for slot=1,8 do
    local row=state.roster[slot]
    local handle=validation.integer(state.handles[slot],-2147483648,2147483647,'recorded transport handle')
    assert(type(row)=='table' and row.slot==slot,'Recorded roster slot differs')
    validation.integer(row.ai,0,2147483647,'recorded AI')
    validation.integer(row.variation,0,2147483647,'recorded AI variation')
    local kind=handle~=-1 and 'human' or (row.ai~=0 and 'ai' or 'empty')
    assert(row.kind==kind,'Recorded roster kind differs')
    if kind=='human' then
      assert(handle~=0 and not seen[handle],'Ambiguous recorded human handle')
      seen[handle]=true
    end
    result.handles[slot]=kind=='human' and slot or -1
    result.roster[slot]={slot=slot,kind=kind,ai=row.ai,variation=row.variation}
  end
  assert(result.roster[result.localPlayer].kind=='human','Recorded local player is not human')
  return result
end

function M.install(engine)
  if engine.offlineInstalled then return end
  -- Validate the entire boundary before installing the first passive gate.
  local sites=require('code/offline-sites').verify()
  local ordered={}
  for _,site in pairs(sites) do ordered[#ordered+1]=site end
  require('code/fixes').install(ordered,engine.offlineFlag)
  engine.offlineInstalled=true
end

-- The local load handler reconstructs the UI and invokes map-extensions. Its
-- completion can enqueue the local portrait-sharing command (116); suppress
-- that command at the existing queue owner while a replay snapshot is loading.
-- Never bypass the extension-aware file reader or inject another load pipeline.
function M.load(engine,path,roster)
  M.install(engine)
  assert(engine:singlePlayer(),'Offline world loading requires the single-player browser')
  engine.offlineLoading=true
  local ok,reason=xpcall(function()
    engine:loadSnapshot(path)
    M.enter(engine,roster)
  end,debug.traceback)
  engine.offlineLoading=nil
  assert(ok,reason)
end

---@param engine table
---@param roster OfflineRoster Validated once before any world loading.
function M.enter(engine,roster)
  assert(engine.offlineInstalled and engine:singlePlayer(),'Offline replay must start from a local loaded world')
  assert(engine:player()==roster.localPlayer,'Loaded replay local player differs')
  for slot=1,8 do
    assert(core.readInteger(engine.base+0x714+slot*4)==roster.roster[slot].ai
      and core.readInteger(engine.base+0x738+slot*4)==roster.roster[slot].variation,
      'Loaded replay AI roster differs')
  end
  engine.offline={roster=roster,previousMode=core.readInteger(engine.base+0x618)}
  core.writeInteger(engine.offlineFlag,1)
  core.writeInteger(engine.base+0x6a8,-1)
  for slot=1,8 do core.writeInteger(engine.base+0x6a8+slot*4,roster.handles[slot]) end
  -- These fields drive live transfer/wait state rather than saved simulation.
  for _,offset in ipairs({0xb94,0xb98,0xcbc,0xc6c}) do core.writeInteger(engine.base+offset,0) end
  core.writeInteger(engine.base+0x618,roster.mode)
end

function M.leave(engine)
  if not engine.offline then return end
  core.writeInteger(engine.base+0x618,engine.offline.previousMode)
  -- The single-player loader gave only the local slot a virtual handle. Do
  -- not leak the recorded human roster into the next single-player match.
  for slot=0,8 do core.writeInteger(engine.base+0x6a8+slot*4,
    slot==engine.offline.roster.localPlayer and 1 or -1) end
  core.writeInteger(engine.offlineFlag,0)
  engine.offline=nil
end
return M
