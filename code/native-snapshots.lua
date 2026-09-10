-- Native save/load ownership, shared by recording and offline playback.
local M={}

-- Always restore temporary native state, including when a Lua/native wrapper fails.
local function temporarily(run, restore)
  local ok, reason=xpcall(run,debug.traceback)
  restore()
  assert(ok,reason)
end

function M:saveSnapshot(path)
  assert(#path<500 and (self:singlePlayer() or (self.offline and self.offlineInstalled)),
    'Snapshot requires single-player or isolated offline playback')
  local resource=self.sites.resources
  local oldType=core.readInteger(resource+0xbc4)
  local filename=resource+0x7aee0+1001
  local oldName=core.readBytes(filename,1001)
  local oldProgress=core.readInteger(self.sites.packager+0x20)
  local duration=self.sites.gameCore+0x2370
  local oldDuration=core.readInteger(duration)
  core.writeInteger(resource+0xbc4,1)
  core.writeString(filename,path..'\0')
  core.writeInteger(self.sites.packager+0x20,0) -- no progress callback/audio during capture
  temporarily(function() self.saveNative(self.sites.packager,self.sites.sections) end,function()
    core.writeBytes(filename,oldName) -- Restore all bytes of the fixed native array.
    core.writeInteger(resource+0xbc4,oldType)
    core.writeInteger(self.sites.packager+0x20,oldProgress)
    core.writeInteger(duration,oldDuration)
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
  local view=core.readInteger(self.sites.gameCore+0xc)
  local loaded=false
  -- Recovery transitions originate in a running replay. Use the same browser
  -- context as its first load: prepareMap's negative pause sentinel otherwise
  -- permits an unclocked simulation update when the current view is in-game.
  core.writeInteger(self.sites.gameCore+0xc,20)
  temporarily(function()
    self.loadNative(0)
    -- The outer loader builds navigation/rendering caches, but prepareMap also
    -- resets saved simulation fields (e.g. section 1024's tick load balancer).
    -- Reapply the snapshot through the same extension-aware native reader once
    -- that preparation has finished. This preserves saved simulation values
    -- without duplicating its decoder or maintaining a list of reset fields.
    local progress=core.readInteger(self.sites.packager+0x20)
    core.writeInteger(self.sites.packager+0x20,0)
    temporarily(function() self.readWorldNative(self.sites.packager,self.sites.sections) end,
      function() core.writeInteger(self.sites.packager+0x20,progress) end)
    loaded=true
  end,function()
    core.writeInteger(self.pathOverride,0)
    self.loading=false
    self.overridePath=nil
    if not loaded then core.writeInteger(self.sites.gameCore+0xc,view) end
    -- These four fields belong to the load dialog; preserve the game's menu transition.
    for offset,value in pairs(old) do core.writeInteger(state+offset,value) end
  end)
  self:resetCommands()
end

return M
