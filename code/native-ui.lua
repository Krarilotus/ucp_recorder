local native=require('code/native')
local profiles=require('code/ui-sites')
local M={ITEM_SIZE=0x50}

function M.verify()
  -- ui lazily resolves its main-state callable entries on first access (often
  -- Automarket's GUI-loaded callback). Resolve them before we wrap activation;
  -- the cached entry still points to the wrapper and retains both modules' UI.
  if modules and modules.ui then modules.ui:access() end
  local sites=assert(profiles[native.profile.name])
  for name,site in pairs(sites) do
    local actual=core.readBytes(site.address,#site.bytes)
    for i,value in ipairs(site.bytes) do
      assert(actual[i]==value,'Recorder UI conflicts at '..name)
    end
  end
  return sites
end

function M.new(sites,onError)
  local o=setmetatable({sites=sites,onError=onError,dialogs={},textBuffer=core.allocate(1024,true)},{__index=M})
  o.textNative=core.exposeCode(sites.text.address,9,1)
  o.borderNative=core.exposeCode(sites.border.address,6,1)
  o.buttonNative=core.exposeCode(sites.basicButton.address,3,1)
  o.menuConstructor=core.exposeCode(sites.menuConstructor.address,2,1)
  o.modalConstructor=core.exposeCode(sites.modalConstructor.address,10,1)
  o.activateNative=core.exposeCode(sites.activateModal.address,3,1)
  return o
end

function M:callback(callback)
  return utils.createLuaFunctionWrapper(function(registers)
    local ok,reason=xpcall(function() callback(registers) end,debug.traceback)
    if not ok then self.onError(reason) end
    return registers
  end)
end

function M:text(label,x,y,alignment)
  label=tostring(label):gsub('[\r\n%z]',' '):sub(1,150)
  core.writeString(self.textBuffer,label..'\0')
  -- Font slots 0..14 are uninitialized in the HD menus. Slot 19 is the
  -- game's 16-pixel antialiased font; text expects BGR24, unlike RGB15 borders.
  self.textNative(self.sites.textManager.value,self.textBuffer,x+1,y+1,alignment or 0,0,19,0,0)
  self.textNative(self.sites.textManager.value,self.textBuffer,x,y,alignment or 0,0x9AD7E4,19,0,0)
end

function M:button(address,x,y,width,height,label,action,selected)
  for offset=0,self.ITEM_SIZE-4,4 do core.writeInteger(address+offset,0) end
  core.writeInteger(address,3)
  core.writeInteger(address+4,x); core.writeInteger(address+8,y)
  core.writeInteger(address+12,width); core.writeInteger(address+16,height)
  core.writeInteger(address+20,self:callback(action))
  core.writeInteger(address+28,self:callback(function()
    local state=self.sites.buttonState.value
    local drawX,drawY=core.readInteger(state),core.readInteger(state+4)
    local text=type(label)=='function' and label() or label
    if text=='' then return end
    -- The same tiled interface_icons3 skin used by the native pause-menu buttons.
    self.buttonNative(self.sites.buttonSurface.value,0,-1)
    local color=core.readSmallInteger(self.sites.gold.value)%65536
    local hover=core.readInteger(state+16)~=0
    self.borderNative(self.sites.pencil.value,drawX,drawY,drawX+width-1,drawY+height-1,color)
    if hover or (selected and selected()) then
      self.borderNative(self.sites.pencil.value,drawX+2,drawY+2,drawX+width-3,drawY+height-3,color)
    end
    self:text(text,drawX+8,drawY+math.floor((height-12)/2))
  end))
  core.writeInteger(address+36,1) -- SIMPLE_RENDER, native button coordinates
  core.writeSmallInteger(address+48,0xfff0) -- no user-control lookup
end

function M:modal(items,count,width,height,render)
  assert(count==#items,'Replay dialog item count differs')
  local menu=core.allocate(0x44,true)
  local array=core.allocate((count+1)*self.ITEM_SIZE,true)
  for i,item in ipairs(items) do
    local address=array+(i-1)*self.ITEM_SIZE
    self:button(address,item.x,item.y,item.width,item.height,item.label,item.action,item.selected)
    core.writeInteger(address+0x4c,menu)
  end
  core.writeInteger(array+count*self.ITEM_SIZE,0x66)
  self.menuConstructor(menu,array)
  local used={}
  for id in pairs(self.dialogs) do used[id]=true end
  local pointer=core.readInteger(self.sites.modalStack.value)
  local seen={}; local entries=0
  while pointer~=0 and pointer~=-1 and pointer~=0xffffffff do
    entries=entries+1; assert(entries<1024,'Native modal list is too long')
    assert(not seen[pointer],'Cyclic native modal list'); seen[pointer]=true
    used[core.readInteger(pointer)]=true
    pointer=core.readInteger(pointer+0x24)
  end
  local id=300; while used[id] do id=id+1; assert(id<1300,'No replay dialog slot') end
  local dialog=core.allocate(40,true)
  local callback=self:callback(function(registers)
    render(core.readInteger(registers.ESP+4),core.readInteger(registers.ESP+8))
  end)
  -- Native red double frame; centered coordinates and the game's own backdrop.
  self.modalConstructor(dialog,id,-1,-1,width,height,512,0,callback,menu)
  self.dialogs[id]=true
  return id
end

-- Retain the native pause-menu stack when opening a replay submenu.
function M:show(id) self.activateNative(self.sites.modalComposition.value,id,1) end
function M:close() self:show(-1) end

function M:activeDialog()
  return core.readInteger(self.sites.modalComposition.value+0x2c)
end

function M:installInput(singlePlayer,handler)
  local original
  -- WindowProc is stdcall with four stack arguments. UCP's thiscall bridge with
  -- an unused ECX argument has the same stack cleanup (ret 16); native code
  -- never reads incoming ECX. No global game text buffer is borrowed.
  original=core.hookCode(function(unused,window,message,key,data)
    if singlePlayer() and self.dialogs[self:activeDialog()]
      and (message==0x100 or message==0x101 or message==0x102) then
      local ok,reason=pcall(handler,message,key)
      if not ok then self.onError(reason) end
      return 0
    end
    return original(unused,window,message,key,data)
  end,self.sites.windowProc.address,5,1,#self.sites.windowProc.bytes)
end

function M:extendPause(label,action,predicate)
  local size=10*self.ITEM_SIZE -- original nine entries plus sentinel
  local array=core.allocate(size+self.ITEM_SIZE,true)
  core.copyMemory(array,self.sites.pauseArray.value,size)
  local item=array+size-self.ITEM_SIZE
  core.copyMemory(item+self.ITEM_SIZE,item,self.ITEM_SIZE)
  self:button(item,100,342,300,27,label,action)
  core.writeCode(self.sites.pauseArray.address,{
    core.AssemblyLambda('push array',{array=array})
  })
  self:trackVisibility({item},predicate)
  local original
  original=core.hookCode(function(this,id,retain)
    if id==5 then
      core.writeInteger(self.sites.pauseModal.value+0x10,predicate() and 405 or 357)
    end
    return original(this,id,retain)
  end,self.sites.activateModal.address,3,1,#self.sites.activateModal.bytes)
end

function M:trackVisibility(referenceItems,predicate)
  local callbacks={}
  for _,item in ipairs(referenceItems) do callbacks[core.readInteger(item+20)]=true end
  self.visibilityGroups=self.visibilityGroups or {}
  self.visibilityGroups[#self.visibilityGroups+1]={items=referenceItems,callbacks=callbacks,predicate=predicate}
  if self.visibilityInstalled then return end
  self.visibilityInstalled=true
  local original
  original=core.hookCode(function(this,action)
    for _,group in ipairs(self.visibilityGroups) do
      if this==core.readInteger(group.items[1]+0x4c) then
        local ok,reason=pcall(function()
          local item=core.readInteger(this)
          local visible=group.predicate()
          -- Find our callbacks in the current array, allowing other modules to
          -- reallocate or append items. A negative type skips only this item.
          for _=1,4096 do
            local kind=core.readInteger(item)
            if kind==0x66 then return end
            if group.callbacks[core.readInteger(item+20)] then
              core.writeInteger(item,visible and 3 or -2147483645)
            end
            item=item+self.ITEM_SIZE
          end
          error('Replay menu array has no terminator')
        end)
        if not ok then self.onError(reason) end
      end
    end
    return original(this,action)
  end,self.sites.handleMenu.address,2,1,#self.sites.handleMenu.bytes)
end
return M
