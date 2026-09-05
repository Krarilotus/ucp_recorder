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
  for name, site in pairs(sites) do
    if type(site)=='table' then
      local actual=core.readBytes(site.address, #site.bytes)
      for i, value in ipairs(site.bytes) do
        assert(actual[i]==value, 'Recorder session hook conflicts at ' .. name)
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
  e.pendingSlots={}
  return setmetatable(e,{__index=M})
end

function M:tick() return core.readInteger(native.addr(0x1fe7da8)) end
function M:player() return core.readInteger(native.addr(0x1a275dc)) end
function M:singlePlayer()
  local mode=core.readInteger(self.base+0x618)
  return mode==0 or mode==99
end
function M:pause() core.writeInteger(self.sites.paused,1) end

function M:rngState()
  return {core.readSmallInteger(self.rng),core.readSmallInteger(self.rng+2),
    core.readInteger(self.rng+0x9c48),core.readInteger(self.rng+0x9c4c)}
end

function M:saveSnapshot(path)
  assert(#path<500 and self:singlePlayer(), 'Snapshot requires a single-player game')
  local resource=self.sites.resources
  local oldType=core.readInteger(resource+0xbc4)
  local filename=resource+0x7aee0+1001
  local oldName=core.readBytes(filename,1001)
  local oldProgress=core.readInteger(self.sites.packager+0x20)
  core.writeInteger(resource+0xbc4,1)
  core.writeString(filename,path)
  core.writeInteger(self.sites.packager+0x20,0) -- no progress callback/audio during capture
  temporarily(function() self.saveNative(self.sites.packager,self.sites.sections) end,function()
    core.writeBytes(filename,oldName) -- writeString would add a byte past this fixed array.
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
  core.writeString(self.pathBuffer,path)
  core.writeInteger(state+0x58,31) -- native Load action
  core.writeInteger(state+0x7c,1)
  core.writeInteger(state+0x80,0)
  core.writeInteger(state+0x884,0)
  self.loading=true
  temporarily(function() self.loadNative(0) end,function()
    self.loading=false
    self.overridePath=nil
    -- These four fields belong to the load dialog; preserve the game's menu transition.
    for offset,value in pairs(old) do core.writeInteger(state+offset,value) end
  end)
  self.pendingSlots={}
end

function M:canSchedule()
  local index=core.readInteger(self.base+self.sites.writeIndexOffset)
  if index<0 or index>=200 then return false end
  local state=core.readByte(self.base+0x3c67c+index*1272+9)
  return state==0 or state>=10
end

function M:scheduleCommand(command)
  require('code/validation').command(command)
  assert(self:canSchedule(),'Native command ring is full')
  local bytes=require('code/utils').hexToTable(command.data)
  for i=#bytes+1,1260 do bytes[i]=0 end
  core.writeBytes(self.buffer,bytes)
  local slot=core.readInteger(self.base+self.sites.writeIndexOffset)
  self.expectedSize=command.size
  self.copyError=nil
  temporarily(function()
    self.schedule(self.base,command.commandCategory,command.player,command.time,self.buffer)
  end,function() self.expectedSize=nil end)
  if self.copyError then
    core.writeByte(self.base+0x3c67c+slot*1272+9,10)
    error(self.copyError)
  end
  self.pendingSlots[slot]=true
end

function M:commandsPending()
  for slot in pairs(self.pendingSlots) do
    local state=core.readByte(self.base+0x3c67c+slot*1272+9)
    if state>0 and state<10 then return true end
    self.pendingSlots[slot]=nil
  end
  return false
end

function M:install(recorder)
  local originalFileName, originalMapName, originalQueue
  originalFileName=core.hookCode(function(this)
    if self.overridePath and core.readInteger(this+0xbc4)==1 then return self.pathBuffer end
    return originalFileName(this)
  end,self.sites.fileName.address,1,1,#self.sites.fileName.bytes)
  local dummy=core.allocate(16,true); core.writeString(dummy,'replay')
  originalMapName=core.hookCode(function(this,index)
    if self.overridePath then return dummy end
    return originalMapName(this,index)
  end,self.sites.mapName.address,2,1,#self.sites.mapName.bytes)
  originalQueue=core.hookCode(function(this,category)
    if recorder.mode=='play' and not self.loading then return 0 end
    return originalQueue(this,category)
  end,self.sites.queue.address,2,1,#self.sites.queue.bytes)
  -- Replace exactly MOV EAX,[ESI+commandSize] before the timed payload copy.
  -- A corrupt record cannot cause a native read beyond its declared payload.
  core.writeCode(self.sites.copySize.address,{0x90,0x90,0x90,0x90,0x90,0x90})
  core.detourCode(function(registers)
    local size=core.readInteger(registers.ESI+0x2d830)
    if self.expectedSize and registers.EDX==self.buffer and size~=self.expectedSize then
      self.copyError='Native payload size differs from replay record'
      size=0
    end
    registers.EAX=size
    return registers
  end,self.sites.copySize.address,6)
end

return M
