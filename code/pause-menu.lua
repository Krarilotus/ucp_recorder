-- Attach to the initialized menu through UI's existing insertion owner.
local M={}

function M.attach(ui,label,action,predicate,isPlayback)
  local ffi=modules.cffi:cffi()
  local access=modules.ui:access()
  local modal=assert(access.manager.lookupModalMenu(5),'Native pause menu is unavailable')
  local menu=access.api.ui.Menu:fromPointer(modal.pointerToMenu,5)
  local count=menu.menuItemsIndex
  assert(count>=9 and count<4096,'Unsupported native pause menu size')
  local function address(item) return ffi.tonumber(ffi.cast('unsigned long',ffi.addressof(item))) end
  local originalRestart=core.allocate(ui.ITEM_SIZE,true)
  local disabledRestart=core.allocate(ui.ITEM_SIZE,true)
  local restart
  for index=0,count-1 do
    local item=address(menu.menuItems[index])
    if core.readInteger(item+4)==100 and core.readInteger(item+8)==206
      and core.readInteger(item+12)==300 and core.readInteger(item+16)==27 then
      assert(not restart,'Ambiguous native restart control');restart=item
    end
  end
  assert(restart,'Native restart control is unavailable')
  -- afterInit follows native construction, including inherited callbacks.
  core.copyMemory(originalRestart,restart,ui.ITEM_SIZE)
  ui:button(disabledRestart,100,206,300,27,function() return require('code/locale').text('Restart mission') end,
    function() end,nil,nil,function() return false end)
  core.writeInteger(disabledRestart+0x4c,core.readInteger(restart+0x4c))
  local template=core.allocate(ui.ITEM_SIZE,true)
  ui:button(template,100,modal.height-15,300,27,label,action)
  menu:insertMenuItem(count,ffi.cast('MenuItem *',template)[0])
  local item=address(menu.menuItems[count])
  ui:trackVisibility({item},predicate)
  -- Pin the owner and its allocation even if another module later reallocates.
  local state={menu=menu,modal=modal,extraHeight=0,disabled=false}
  function state.activate()
    local extra=predicate() and 48 or 0
    modal.height=modal.height+extra-state.extraHeight;state.extraHeight=extra
    if not isPlayback then return end
    local disable=isPlayback()
    if disable==state.disabled then return end
    local source=state.disabled and disabledRestart or originalRestart
    local target=disable and disabledRestart or originalRestart
    local current=ffi.tonumber(ffi.cast('unsigned long',menu.menu.menuItemArray))
    for _=1,4096 do
      if core.readInteger(current)==0x66 then break end
      if core.readInteger(current+4)==100 and core.readInteger(current+8)==206
        and core.readInteger(current+20)==core.readInteger(source+20)
        and core.readInteger(current+28)==core.readInteger(source+28) then
        core.copyMemory(current,target,ui.ITEM_SIZE)
        state.disabled=disable;return
      end
      current=current+ui.ITEM_SIZE
    end
    error('Native restart control changed during replay')
  end
  return state
end

return M
