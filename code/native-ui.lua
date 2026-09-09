local native=require('code/native')
local profiles=require('code/ui-sites')
local M={ITEM_SIZE=0x50}

function M.verify()
  -- ui lazily resolves its main-state callable entries on first access (often
  -- Automarket's GUI-loaded callback). Resolve them before we wrap activation;
  -- the cached entry still points to the wrapper and retains both modules' UI.
  assert(modules and modules.ui,'Recorder menus require UI 1.0.1 and its dependencies')
  modules.ui:access()
  local sites=assert(profiles[native.profile.name])
  for name,site in pairs(sites) do
    require('code/hook-check').verify(site,'Recorder UI conflicts at '..name)
  end
  return sites
end

function M.new(sites,onError)
  local o=setmetatable({sites=sites,onError=onError,dialogs={},textBuffer=core.allocate(1024,true)},{__index=M})
  o.textNative=core.exposeCode(sites.text.address,9,1)
  o.widthNative=core.exposeCode(sites.textWidth.address,3,1)
  o.headerNative=core.exposeCode(sites.header.address,5,1)
  o.borderNative=core.exposeCode(sites.border.address,6,1)
  o.buttonNative=core.exposeCode(sites.basicButton.address,3,1)
  o.menuConstructor=core.exposeCode(sites.menuConstructor.address,2,1)
  o.modalConstructor=core.exposeCode(sites.modalConstructor.address,10,1)
  o.activateNative=core.exposeCode(sites.activateModal.address,3,1)
  o.avatarNative=core.exposeCode(sites.avatar.address,3,0)
  return o
end

function M:sprite(gm,picture,x,y)
  local game=modules.ui:access().game
  game.Rendering.renderGM(game.Rendering.textureRenderCore,gm,picture,x,y)
end

function M:border(x,y,width,height)
  local gold=core.readSmallInteger(self.sites.gold.value)%65536
  self.borderNative(self.sites.pencil.value,x,y,x+width,y+height,gold)
end

-- Register now, attach only after the game's constructors have populated the
-- menu. Use the UI module's registry so this also respects other extensions.
function M:attachOverlay(menuIDs,items,visible,screenInput)
  local ffi=modules.cffi:cffi()
  local manager=modules.ui:access().manager
  self.overlays=self.overlays or {}
  for _,id in ipairs(menuIDs) do
    local pointer=manager.lookupMenu(id)
    local menu=assert(ffi.tonumber(ffi.cast('unsigned long',pointer)))
    self.overlays[menu]={items=items,visible=visible}
    if screenInput then
      self.inputOverlays=self.inputOverlays or {}
      self.inputOverlays[id]=menu
    end
  end
end

function M:renderOverlayItem(item)
  local state=self.sites.buttonState.value
  item.render(core.readInteger(state)+(self.overlayOriginX or 0),
    core.readInteger(state+4)+(self.overlayOriginY or 0))
end

function M:windowAddress()
  local bytes=self.sites.buildingAndStatus.bytes
  return bytes[3]+bytes[4]*256+bytes[5]*65536+bytes[6]*16777216-0x5c
end

-- Scope the complete overlay, not every glyph/portrait. FontSizeClass::renderText
-- independently selects TextManager.textSurfaceTarget and its horizontal clip.
-- Native callbacks following us must see their original surface/clip/text cursor.
function M:renderOverlay(overlay,render)
  local target=modules.ui:access().game.Rendering.pDrawBufferChoiceValue
  local previous=target[0]
  -- Front-end controls belong to SCREEN_MENU. During gameplay only the native
  -- menu's declared overlap rectangles are copied from that surface to the map
  -- (TextureRenderCore::moveOverlappingMenuPartsToMapSurface). Screen-space HUD
  -- controls outside those rectangles must draw directly to MAP_GAME.
  local surface=overlay.items[1].frontEnd and 0 or 1
  -- MAP_GAME is a scrolled backing surface. The native menu-to-map copy adds
  -- this viewport origin too. Only drawing uses it; mouse hitboxes stay in
  -- screen space, so panning cannot move the player's controls.
  local oldX,oldY=self.overlayOriginX,self.overlayOriginY
  local x,y=0,0
  if surface==1 then
    x=core.readInteger(self.sites.mapViewport.value)
    y=core.readInteger(self.sites.mapViewport.value+4)
  end
  self.overlayOriginX,self.overlayOriginY=x,y
  local text=self.sites.textManager.value
  local cursor=core.readInteger(text)
  local left,right=core.readInteger(text+8),core.readInteger(text+12)
  local textSurface=core.readInteger(text+28)
  target[0]=surface
  core.writeInteger(text+28,surface)
  core.writeInteger(text+8,x)
  core.writeInteger(text+12,x+core.readInteger(self:windowAddress()+0x18))
  local ok,reason=pcall(render)
  core.writeInteger(text,cursor)
  core.writeInteger(text+8,left); core.writeInteger(text+12,right)
  core.writeInteger(text+28,textSurface)
  target[0]=previous
  self.overlayOriginX,self.overlayOriginY=oldX,oldY
  assert(ok,reason)
end

function M:updateOverlay(menu,action)
  -- Gameplay renders the root view, but sends input to its selected build/book
  -- tab. Resolve screen-wide controls from that root before native tab input;
  -- attaching them only to the root renderer never receives gameplay clicks.
  if action==0 and self.inputOverlays then
    menu=self.inputOverlays[core.readInteger(native.addr(0x1fe7d1c))] or menu
  end
  local overlay=self.overlays and self.overlays[menu]
  if not overlay or not overlay.visible() then return end
  if not overlay.array then
    local array=core.allocate((#overlay.items+1)*self.ITEM_SIZE,true)
    overlay.menu=core.allocate(0x44,true)
    for index,item in ipairs(overlay.items) do
      local address=array+(index-1)*self.ITEM_SIZE
      self:button(address,item.x,item.y,item.width,item.height,item.label or '',function()
        overlay.consumed=true
        if item.action then item.action() end
      end,nil,nil,item.enabled==false and function() return false end or item.enabled)
      core.writeInteger(address+0x4c,overlay.menu)
      if item.render then core.writeInteger(address+28,self:callback(function()
        self:renderOverlayItem(item)
      end)) end
    end
    core.writeInteger(array+#overlay.items*self.ITEM_SIZE,0x66)
    self.menuConstructor(overlay.menu,array)
    overlay.array=array
    overlay.layout={}
  end
  -- The book and build menu have different offsets. Place these controls in
  -- screen space while leaving the native menu's own origin untouched.
  local window=self:windowAddress()
  local width=core.readInteger(window+0x18)
  local height=core.readInteger(window+0x1c)
  local frontX=core.readInteger(window+0x20)
  local frontY=core.readInteger(window+0x24)
  for index,item in ipairs(overlay.items) do
    local address=overlay.array+(index-1)*self.ITEM_SIZE
    local kind=(not item.visible or item.visible()) and 3 or -2147483645
    local x,y=item.x,item.y
    if item.position then x,y=item.position(width,height) end
    if x<0 then x=width+x end
    if item.frontEnd then
      x=x+frontX
      y=y+frontY
    end
    local previous=overlay.layout[index] or {}
    if previous.kind~=kind then core.writeInteger(address,kind); previous.kind=kind end
    if previous.x~=x then core.writeInteger(address+4,x); previous.x=x end
    if previous.y~=y then core.writeInteger(address+8,y); previous.y=y end
    overlay.layout[index]=previous
  end
  return overlay
end

function M:callback(callback)
  return utils.createLuaFunctionWrapper(function(registers)
    local ok,reason=xpcall(function() callback(registers) end,debug.traceback)
    if not ok then self.onError(reason) end
    return registers
  end)
end

function M:text(label,x,y,alignment,font,hover,maxWidth,disabled,blend,color)
  label=require('code/locale').native(label)
  label=tostring(label):gsub('[\r\n%z]',' '):sub(1,150)
  core.writeString(self.textBuffer,label..'\0')
  if maxWidth then
    local function width() return self.widthNative(self.sites.textManager.value,self.textBuffer,font or 18) end
    if width()>maxWidth then
      repeat
        label=label:sub(1,-2)
        core.writeString(self.textBuffer,label..'...\0')
      until #label==0 or width()<=maxWidth
    end
  end
  -- Match native OptionsMenu_Buttons: font18, BGR24 colors and native blending.
  -- Alignment1 is centered on x; a positive width centers inside that width.
  self.textNative(self.sites.textManager.value,self.textBuffer,x,y,alignment or 0,
    color or (disabled and 0x7F7F7F or (hover and 0xCCFAFF or 0xC2F0EB)),font or 18,0,
    blend or (disabled and 0 or (hover and 2 or 4)))
end

-- Terrain needs opaque lettering with a dark edge, unlike shaded menu panels.
function M:hudText(label,x,y,alignment,maxWidth)
  self:text(label,x+1,y+1,alignment,18,false,maxWidth,false,0,0)
  self:text(label,x,y,alignment,18,false,maxWidth,false,0,0xCCF4FF)
end

function M:header(label,x,y,width)
  -- Original Options dialog banner: tiled interface_icons3, shields and font15.
  -- The native function accepts four stack arguments and cleans all four.
  self.headerNative(self.sites.pencil.value,x,y,width,0)
  self:text(label,x+math.floor(width/2),y+22,1,15,false,width-100,false,0)
end

function M:button(address,x,y,width,height,label,action,selected,leftAligned,enabled)
  for offset=0,self.ITEM_SIZE-4,4 do core.writeInteger(address+offset,0) end
  core.writeInteger(address,3)
  core.writeInteger(address+4,x); core.writeInteger(address+8,y)
  core.writeInteger(address+12,width); core.writeInteger(address+16,height)
  core.writeInteger(address+20,self:callback(function() if not enabled or enabled() then action() end end))
  core.writeInteger(address+28,self:callback(function()
    local state=self.sites.buttonState.value
    local originalX,originalY=core.readInteger(state),core.readInteger(state+4)
    local drawX=originalX+(self.overlayOriginX or 0)
    local drawY=originalY+(self.overlayOriginY or 0)
    local text=type(label)=='function' and label() or label
    if text=='' then return end
    -- The same tiled interface_icons3 skin used by the native pause-menu buttons.
    local interactive=not enabled or enabled()
    local previousHover=core.readInteger(state+16)
    if not interactive then core.writeInteger(state+16,0) end
    -- Native button backgrounds read shared coordinates themselves. Translate
    -- drawing through the same viewport as custom HUD items; keep hitboxes and
    -- the next native renderer in screen coordinates.
    local translated=drawX~=originalX or drawY~=originalY
    if translated then core.writeInteger(state,drawX); core.writeInteger(state+4,drawY) end
    local ok,reason=pcall(self.buttonNative,self.sites.buttonSurface.value,0,-1)
    if translated then core.writeInteger(state,originalX); core.writeInteger(state+4,originalY) end
    if not interactive then core.writeInteger(state+16,previousHover) end
    assert(ok,reason)
    local color=core.readSmallInteger(self.sites.gold.value)%65536
    local hover=core.readInteger(state+16)~=0
    if selected and selected() then
      self.borderNative(self.sites.pencil.value,drawX+2,drawY+2,drawX+width-3,drawY+height-3,color)
    end
    self:text(text,leftAligned and drawX+8 or drawX+math.floor(width/2),
      drawY+math.floor((height-13)/2),leftAligned and 0 or 1,18,hover,width-16,not interactive)
  end))
  core.writeInteger(address+36,1) -- SIMPLE_RENDER, native button coordinates
  core.writeSmallInteger(address+48,0xfff0) -- no user-control lookup
end

function M:modal(items,count,width,height,render,title)
  assert(count==#items,'Replay dialog item count differs')
  local contentOffset=title and 32 or 0
  local menu=core.allocate(0x44,true)
  local array=core.allocate((count+1)*self.ITEM_SIZE,true)
  for i,item in ipairs(items) do
    local address=array+(i-1)*self.ITEM_SIZE
    self:button(address,item.x,item.y+contentOffset,item.width,item.height,item.label,item.action,item.selected,item.leftAligned,item.enabled)
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
    local x,y=core.readInteger(registers.ESP+4),core.readInteger(registers.ESP+8)
    if title then self:header(type(title)=='function' and title() or title,x,y,width) end
    render(x,y+contentOffset)
  end)
  -- Native red double frame; centered coordinates and the game's own backdrop.
  self.modalConstructor(dialog,id,-1,-1,width,height+contentOffset,512,0,callback,menu)
  self.dialogs[id]=true
  return id
end

-- Retain the native pause-menu stack when opening a replay submenu.
function M:show(id) self.activateNative(self.sites.modalComposition.value,id,1) end
function M:close() self:show(-1) end

function M:activeDialog()
  return core.readInteger(self.sites.modalComposition.value+0x2c)
end

function M:installViewRender()
  -- Both the summary strip and the book/building details have their own
  -- rendering owners outside handleMenuItems. Scope only these render calls;
  -- input callbacks and command execution retain the recorded actor.
  for _,name in ipairs({'playerSummary','buildingAndStatus'}) do
    local site=self.sites[name]
    local original
    original=core.hookCode(function()
      return self.renderScope(function() return original() end)
    end,site.address,0,0,#site.bytes)
  end
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
    if self.onNativeKey then
      local ok,handled=pcall(self.onNativeKey,message,key)
      if not ok then self.onError(handled) elseif handled then return 0 end
    end
    return original(unused,window,message,key,data)
  end,self.sites.windowProc.address,5,1,#self.sites.windowProc.bytes)
end

function M:extendPause(label,action,predicate,isPlayback)
  local size=10*self.ITEM_SIZE -- original nine entries plus sentinel
  local array=core.allocate(size+self.ITEM_SIZE,true)
  core.copyMemory(array,self.sites.pauseArray.value,size)
  local restart,originalRestart,disabledRestart,restartDisabled
  if isPlayback then
    restart=array+5*self.ITEM_SIZE
    originalRestart=core.allocate(self.ITEM_SIZE,true)
    disabledRestart=core.allocate(self.ITEM_SIZE,true)
    self:button(disabledRestart,100,206,300,27,function() return require('code/locale').text('Restart mission') end,
      function() end,nil,nil,function() return false end)
  end
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
      if restart then
        if isPlayback() and not restartDisabled then
          -- The constructor fills inherited action/render callbacks. Preserve
          -- that initialized row, never the earlier static template (null callbacks).
          core.copyMemory(originalRestart,restart,self.ITEM_SIZE)
          core.copyMemory(restart,disabledRestart,self.ITEM_SIZE)
          core.writeInteger(restart+0x4c,core.readInteger(item+0x4c))
          restartDisabled=true
        elseif not isPlayback() and restartDisabled then
          core.copyMemory(restart,originalRestart,self.ITEM_SIZE)
          restartDisabled=false
        end
      end
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
    local overlay=self:updateOverlay(this,action)
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
    local result
    if overlay and action==0 then
      overlay.consumed=false
      original(overlay.menu,action)
    end
    if overlay and action==0 and overlay.consumed then
      -- A portrait/history action owns this click; never also activate the
      -- native control underneath it (particularly the results Next arrow).
    elseif self.renderScope and (action==1 or action==3) then
      result=self.renderScope(function() return original(this,action) end)
    else result=original(this,action) end
    if overlay and action~=0 then
      -- The game's alternate render pass selects flagged native items. Our
      -- separate menu contains ordinary items and must use its ordinary pass.
      if action==1 or action==3 then
        self:renderOverlay(overlay,function() original(overlay.menu,1) end)
      else original(overlay.menu,action) end
    end
    -- Input dispatch has unwound: same game-thread boundary as a native Play
    -- action, outside rendering and outside every simulation tick.
    if action==0 and self.onMenuUpdated then self.onMenuUpdated() end
    return result
  end,self.sites.handleMenu.address,2,1,#self.sites.handleMenu.bytes)
end
return M
