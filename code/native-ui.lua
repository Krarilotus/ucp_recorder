local native=require('code/native')
local profiles=require('code/ui-sites')
local M={ITEM_SIZE=0x50}

function M.verify()
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
  local o=setmetatable({sites=sites,onError=onError,textBuffer=core.allocate(1024,true)},{__index=M})
  o.textNative=core.exposeCode(sites.text.address,9,1)
  o.borderNative=core.exposeCode(sites.border.address,6,1)
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
    local color=core.readSmallInteger(self.sites.gold.value)%65536
    local hover=core.readInteger(state+16)~=0
    if hover or (selected and selected()) then
      self.borderNative(self.sites.pencil.value,drawX,drawY,drawX+width-1,drawY+height-1,color)
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
  return id
end

function M:show(id) self.activateNative(self.sites.modalComposition.value,id,0) end
function M:close() self:show(-1) end

function M:trackVisibility(referenceItems,predicate)
  local callbacks={}
  for _,item in ipairs(referenceItems) do callbacks[core.readInteger(item+20)]=true end
  local original
  original=core.hookCode(function(this,action)
    if this==core.readInteger(referenceItems[1]+0x4c) then
      local ok,reason=pcall(function()
        local item=core.readInteger(this)
        local visible=predicate()
        -- Find our callbacks in the current array, allowing other modules to
        -- reallocate or append items. A negative type skips only this item.
        for _=1,4096 do
          local kind=core.readInteger(item)
          if kind==0x66 then return end
          if callbacks[core.readInteger(item+20)] then
            core.writeInteger(item,visible and 3 or -2147483645)
          end
          item=item+self.ITEM_SIZE
        end
        error('Replay menu array has no terminator')
      end)
      if not ok then self.onError(reason) end
    end
    return original(this,action)
  end,self.sites.handleMenu.address,2,1,#self.sites.handleMenu.bytes)
end
return M
