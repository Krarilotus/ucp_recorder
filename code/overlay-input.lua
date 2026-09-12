-- The complete native menu-input step owns HUD hit testing and gesture capture.
-- Retain native button callbacks; never rewrite physical mouse or game state.
local native=require('code/native')
local M={}

function M.install(ui)
  local original,dispatching,captured
  original=core.hookCode(function(menu)
    if dispatching then return original(menu) end
    local root=ui.inputOverlays[core.readInteger(native.addr(0x1fe7d1c))]
    local overlay=root and ui:updateOverlay(root,0)
    local blocked=false
    if overlay then
      local mouse=ui.sites.mouse.value
      local held=core.readInteger(mouse+0x40)~=0 or core.readInteger(mouse+0x44)~=0
        or core.readInteger(mouse+0x48)~=0
      if captured then blocked=true
      else
        -- The native update clears previous hover state before scanning. Its
        -- inner handleMenuItems call must not route to the overlay again.
        dispatching=true
        local ok,reason=pcall(original,overlay.menu)
        dispatching=false
        assert(ok,reason)
        -- Native modal-composition hit flag, independent of tooltip suppression.
        -- Menu.hoveredItem exists for help text and is not ownership.
        blocked=core.readInteger(ui.sites.menuHit.value)~=0
        if blocked and held then captured=true end
      end
      -- Keep the release frame too, even if dragged off a portrait. Otherwise
      -- the native map receives an orphan release and selects underneath it.
      -- Do not dispatch a captured press again: a seek's native load can reset
      -- mouse history and make the still-held physical button look newly pressed.
      if not held then captured=false end
    else captured=false end
    local result
    if not blocked then result=original(menu) end
    -- Seek/load and completed snapshot publication run after native input unwinds.
    if ui.onMenuUpdated then ui.onMenuUpdated() end
    return result
  end,ui.sites.updateMenu.address,1,1,#ui.sites.updateMenu.bytes)
end
return M
