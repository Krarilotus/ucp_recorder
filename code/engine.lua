local native = require('code/native')
local allSites = require('code/engine-sites')
local M = {}

-- Always restore temporary native state, including when a Lua/native wrapper fails.
local function temporarily(run, restore)
  local ok, reason=xpcall(run,debug.traceback)
  restore()
  assert(ok,reason)
end

function M.verify()
  local sites = assert(allSites[native.profile.name])
  local adapter=require('code/automarket-replay')
  if adapter.version('protocol') then
    assert(core.readByte(sites.execute.address+8)==0xE9,
      'Enable recorder after protocol in the UCP extension order')
  end
  for name, site in pairs(sites) do
    if type(site)=='table' then
      local actual=core.readBytes(site.address, #site.bytes)
      -- map-extensions wraps this callable entry to include extension save data.
      -- We call that entry, never bypass or overwrite its five-byte hook.
      -- RPS hookCode uses CALL rel32 in the shipped framework; other supported
      -- wrappers use JMP rel32. Keep the untouched sixth byte checked below.
      local wrappedSave=name=='save' and adapter.saveHookAvailable()
        and (actual[1]==0xE8 or actual[1]==0xE9)
      for i, value in ipairs(site.bytes) do
        assert((wrappedSave and i<=5) or actual[i]==value, 'Recorder session hook conflicts at ' .. name)
      end
    end
  end
  return sites
end

function M.new(sites)
  local e={sites=sites, base=native.addr(0x191d768), rng=native.addr(0x1a279c0)}
  e.schedule=core.exposeCode(native.addr(0x480210),5,1)
  e.saveNative=core.exposeCode(sites.save.address,2,1)
  e.loadNative=core.exposeCode(sites.load.address,1,0)
  e.buffer=core.allocate(1260,true)
  e.pathBuffer=core.allocate(512,true)
  e.pathOverride=core.allocate(4,true)
  e.scope=core.allocate(4,true)
  M.resetCommands(e)
  return setmetatable(e,{__index=M})
end

function M:resetCommands()
  if self.trace then self.trace:observe('stop','game/session transition') end
  self.journal=require('code/command-journal').new()
  self.received={}
  self.executing=nil
end

function M:tick() return core.readInteger(native.addr(0x1fe7da8)) end
function M:player() return core.readInteger(native.addr(0x1a275dc)) end
function M:singlePlayer()
  local mode=core.readInteger(self.base+0x618)
  return mode==0 or mode==99
end
function M:setScope(active)
  assert(not active or self:singlePlayer(),'Replay simulation scope requires single-player')
  core.writeInteger(self.scope,active and 1 or 0)
end
function M:pause()
  if self:singlePlayer() then core.writeInteger(self.sites.paused,1) end
end

function M:rngState()
  return {core.readSmallInteger(self.rng),core.readSmallInteger(self.rng+2),
    core.readInteger(self.rng+0x9c48),core.readInteger(self.rng+0x9c4c)}
end

function M:rngData()
  local data=core.readString(self.rng,0x9c50)
  assert(type(data)=='string' and #data==0x9c50,'Incomplete native RNG state')
  return data
end

function M:resourceState()
  local values={}
  for player=1,8 do
    for resource=0,24 do
      values[#values+1]=core.readInteger(self.sites.playerResources+player*0x39f4+resource*4)
    end
  end
  return values
end

function M:networkState()
  local state={mode=core.readInteger(self.base+0x618),localPlayer=self:player(),
    syncStatus=core.readInteger(self.base+0xb98),handles={},roster={}}
  for slot=1,8 do
    local handle=core.readInteger(self.base+0x6a8+slot*4)
    local ai=core.readInteger(self.base+0x714+slot*4)
    state.handles[slot]=handle
    state.roster[slot]={slot=slot,kind=handle~=-1 and 'human' or (ai~=0 and 'ai' or 'empty'),
      ai=ai,variation=core.readInteger(self.base+0x738+slot*4)}
  end
  return state
end

function M:saveSnapshot(path)
  assert(#path<500 and self:singlePlayer(), 'Snapshot requires a single-player game')
  local resource=self.sites.resources
  local oldType=core.readInteger(resource+0xbc4)
  local filename=resource+0x7aee0+1001
  local oldName=core.readBytes(filename,1001)
  local oldProgress=core.readInteger(self.sites.packager+0x20)
  core.writeInteger(resource+0xbc4,1)
  core.writeString(filename,path..'\0')
  core.writeInteger(self.sites.packager+0x20,0) -- no progress callback/audio during capture
  temporarily(function() self.saveNative(self.sites.packager,self.sites.sections) end,function()
    core.writeBytes(filename,oldName) -- Restore all bytes of the fixed native array.
    core.writeInteger(resource+0xbc4,oldType)
    core.writeInteger(self.sites.packager+0x20,oldProgress)
  end)
  local f=assert(io.open(path,'rb'),'Native save did not produce a starting snapshot')
  local size=f:seek('end'); local closed=f:close()
  assert(size and size>1000 and closed,'Native starting snapshot is incomplete')
end

function M:loadSnapshot(path)
  assert(#path<500 and self:singlePlayer(), 'Snapshot requires a single-player game')
  local state=self.sites.menuText
  local old={}
  for _,offset in ipairs({0x58,0x7c,0x80,0x884}) do old[offset]=core.readInteger(state+offset) end
  self.overridePath=path
  core.writeString(self.pathBuffer,path..'\0')
  core.writeInteger(state+0x58,31) -- native Load action
  core.writeInteger(state+0x7c,1)
  core.writeInteger(state+0x80,0)
  core.writeInteger(state+0x884,0)
  self.loading=true
  core.writeInteger(self.pathOverride,1)
  temporarily(function() self.loadNative(0) end,function()
    core.writeInteger(self.pathOverride,0)
    self.loading=false
    self.overridePath=nil
    -- These four fields belong to the load dialog; preserve the game's menu transition.
    for offset,value in pairs(old) do core.writeInteger(state+offset,value) end
  end)
  self:resetCommands()
end

function M:canSchedule()
  local index=core.readInteger(self.base+self.sites.writeIndexOffset)
  if index<0 or index>=200 then return false end
  if self.journal.slots[index] then return false end
  local state=core.readByte(self.base+0x3c67c+index*1272+9)
  return state==0 or state==10
end

function M:validateQueued(slot,command)
  local address=self.base+0x3c67c+slot*1272
  assert(core.readByte(address+9)==1,'Replay ring entry is not pending')
  assert(core.readInteger(address)==command.time,'Native command scheduling tick changed')
  assert(core.readInteger(address+4)==command.player,'Native replay sender changed')
  assert(core.readByte(address+8)==command.commandCategory,'Native replay category changed')
  assert(require('code/utils').tableToHex(core.readBytes(address+10,command.size)):upper()==command.data:upper(),
    'Native replay payload changed')
end

function M:scheduleCommand(command)
  require('code/validation').command(command)
  assert(self:singlePlayer(),'Replay enqueue requires single-player')
  assert(self.expectedSize==nil,'Nested replay enqueue is unsupported')
  assert(self:canSchedule(),'Native command ring is full')
  local bytes=require('code/utils').hexToTable(command.data)
  for i=#bytes+1,1260 do bytes[i]=0 end
  core.writeBytes(self.buffer,bytes)
  local slot=core.readInteger(self.base+self.sites.writeIndexOffset)
  local address=self.base+0x3c67c+slot*1272
  local oldSlot=core.readBytes(address,1272)
  local scratch={}
  for _,offset in ipairs({self.sites.writeIndexOffset,0x2d824,0x2d828,0x2d830,self.sites.writeIndexOffset+4}) do
    scratch[offset]=core.readInteger(self.base+offset)
  end
  self.expectedSize=command.size
  self.copyError=nil; self.copySeen=false
  -- protocol 1.0.0's receive callback reads this native packet buffer even when
  -- the scheduler was given a different pointer. Restore it after the copy.
  local received=self.base+0xcdc
  local oldReceived
  if command.commandCategory==122 then
    oldReceived=core.readBytes(received,1260)
  end
  local ok,reason=xpcall(function()
    if oldReceived then core.writeBytes(received,bytes) end
    self.schedule(self.base,command.commandCategory,command.player,command.time,self.buffer)
    assert(not self.copyError,self.copyError)
    assert(self.copySeen,'Native scheduler did not copy the replay payload')
    assert(core.readInteger(self.base+self.sites.writeIndexOffset)==(slot+1)%200,
      'Native scheduler did not advance exactly one ring slot')
    self:validateQueued(slot,command)
  end,debug.traceback)
  if oldReceived then core.writeBytes(received,oldReceived) end
  self.expectedSize=nil; self.copySeen=nil
  if not ok then
    -- Roll back queue storage/scratch only, not arbitrary effects of a native
    -- handler. The session guard halts playback on any failed enqueue.
    core.writeBytes(address,oldSlot)
    for offset,value in pairs(scratch) do core.writeInteger(self.base+offset,value) end
    error(reason)
  end
  self.journal:queue(slot,command)
end

function M:selectPlayback(recorder)
  assert(self:singlePlayer() and recorder.status=='playing','Replay dispatch is not active')
  recorder:feed()
  local entries=self.journal:select(self:tick())
  -- Reject unknown pending entries before *any* handler in this batch runs.
  for slot=0,199 do
    local state=core.readByte(self.base+0x3c67c+slot*1272+9)
    if state~=0 and state~=10 then
      local source=assert(self.journal.slots[slot],'Untracked native command in replay ring')
      self:validateQueued(slot,source.command)
    end
  end
  for _,item in ipairs(entries) do
    require('code/validation').sessionCommand(item.entry.command,recorder.manifest)
    self:validateQueued(item.slot,item.entry.command)
  end
  for i=0,99 do
    local item=entries[i+1]
    core.writeInteger(self.base+self.sites.selectedOffset+i*8,item and item.slot or 0)
    core.writeInteger(self.base+self.sites.selectedOffset+i*8+4,item and item.entry.command.player or 0)
  end
  core.writeInteger(self.base+self.sites.selectedCountOffset,#entries)
  return #entries>0 and 1 or 0
end

function M:commandsPending()
  return self.journal:pending()
end

function M:abortPlayback()
  if not self:singlePlayer() then return end
  core.writeInteger(self.base+self.sites.selectedCountOffset,0)
  for slot in pairs(self.journal.slots) do
    core.writeByte(self.base+0x3c67c+slot*1272+9,10)
  end
end

function M:beforeCommand(recorder)
  assert(not self.executing,'Nested native command execution is unsupported')
  local slot=require('code/validation').integer(core.readInteger(self.base+0x2d824),0,199,'native ring slot')
  local address=self.base+0x3c67c+slot*1272
  local source=recorder.mode=='play' and self.journal.slots[slot] or self.received[slot]
  assert(source,'Native command has no captured payload/ownership')
  local command=source.command
  local actual={commandCategory=core.readByte(address+8),time=self:tick(),player=core.readInteger(self.base+self.sites.actorOffset),
    size=command.size,data=require('code/utils').tableToHex(core.readBytes(address+10,command.size))}
  require('code/validation').sessionCommand(actual,recorder.manifest)
  assert(core.readInteger(address)==command.time,'Native command scheduling tick changed')
  assert(actual.commandCategory==command.commandCategory and actual.data:upper()==command.data:upper(),
    'Native command changed between receipt and execution')
  if recorder.mode=='play' then self.journal:before(slot,actual) end
  self.executing={slot=slot,source=source,command=actual}
end

function M:captureCommand(size, payload)
  local validation=require('code/validation')
  validation.integer(size,0,1260,'native payload size')
  local slot=validation.integer(core.readInteger(self.base+0x2d824),0,199,'native ring slot')
  local address=self.base+0x3c67c+slot*1272
  self.received[slot]={command={commandCategory=core.readByte(address+8),time=core.readInteger(address),
    size=size,data=require('code/utils').tableToHex(core.readBytes(payload or address+10,size))}}
end

function M:afterCommand(recorder)
  local current=self.executing
  self.executing=nil
  if not current then return end
  if recorder.mode=='play' then self.journal:after(current.slot,current.source)
  else
    self.received[current.slot]=nil
    recorder:onExecutedCommand(current.command)
  end
end

function M:install(recorder)
  local originalQueue
  local resources=require('code/resource-hooks')
  resources.install(self.sites.fileName,self.pathOverride,self.pathBuffer,true)
  local dummy=core.allocate(16,true); core.writeString(dummy,'replay\0')
  resources.install(self.sites.mapName,self.pathOverride,dummy,false)
  originalQueue=core.hookCode(function(this,category)
    if recorder.mode=='play' and self:singlePlayer() and not self.loading then return 0 end
    return originalQueue(this,category)
  end,self.sites.queue.address,2,1,#self.sites.queue.bytes)
  local originalSelect
  originalSelect=core.hookCode(function(this)
    if recorder.mode~='play' or not self:singlePlayer() or self.loading then return originalSelect(this) end
    core.writeInteger(self.base+self.sites.selectedCountOffset,0)
    if recorder.status~='playing' then return 0 end
    local result=0
    local ok=recorder:guard(function()
      assert(this==self.base,'Unexpected replay command receiver')
      result=self:selectPlayback(recorder)
    end)
    return ok and result or 0
  end,self.sites.select.address,1,1,#self.sites.select.bytes)
  -- Local input handlers build payloads directly in the ring. They never pass
  -- through the received-packet copy below, in SP as well as MP. Observe after
  -- that handler returns, before transmission advances the write cursor.
  -- Share this hook with optional MP diagnostics instead of detouring it twice.
  core.detourCode(function(registers)
    if self.trace then self.trace:observe('locallyQueuedCommand') end
    if recorder.active and recorder.status=='recording' and self:singlePlayer() then
      recorder:guard(function()
        self:captureCommand(core.readInteger(self.base+0x2d830))
      end)
    end
    return registers
  end,self.sites.localTimed.address,#self.sites.localTimed.bytes)
  -- Replace exactly MOV EAX,[ESI+commandSize] before the timed payload copy.
  -- A corrupt record cannot cause a native read beyond its declared payload.
  core.writeCode(self.sites.copySize.address,{0x90,0x90,0x90,0x90,0x90,0x90})
  core.detourCode(function(registers)
    local size=core.readInteger(registers.ESI+0x2d830)
    if self.expectedSize then
      self.copySeen=true
      if registers.EDX~=self.buffer or size~=self.expectedSize then
        self.copyError='Native payload size or source differs from replay record'
        size=0
      end
    end
    registers.EAX=size
    if self.trace then self.trace:observe('receivedCommand',registers.EDX,size) end
    if recorder.active and recorder.status=='recording' and self:singlePlayer() then
      local ok=recorder:guard(function()
        self:captureCommand(size,registers.EDX)
      end)
      if not ok then registers.EAX=0 end -- do not copy an invalid native length after stopping
    end
    return registers
  end,self.sites.copySize.address,6)
  -- This instruction precedes protocol's dispatch hook. Leave its hook intact.
  -- On failure use native category 0 (the no-op), preventing the bad dispatch.
  core.writeCode(self.sites.execute.address,{0x90,0x90,0x90,0x90,0x90,0x90,0x90,0x90})
  core.detourCode(function(registers)
    local category=core.readByte(registers.ESI+registers.ECX+0x3c684)
    registers.EDX=category<128 and category or category-256 -- original MOVSX
    if self.trace then self.trace:observe('beforeCommand') end
    if self:singlePlayer() and not self.loading and recorder.active then
      local ok=recorder:guard(function()
        assert(recorder.status=='playing' or recorder.status=='recording','Replay session is stopped')
        self:beforeCommand(recorder)
      end)
      if not ok then registers.EDX=0 end
    end
    return registers
  end,self.sites.execute.address,8)
  core.detourCode(function(registers)
    if self.trace then self.trace:observe('afterCommand') end
    if self:singlePlayer() and not self.loading and recorder.active then
      recorder:guard(function() self:afterCommand(recorder) end)
    end
    return registers
  end,self.sites.executed.address,6)
end

return M
