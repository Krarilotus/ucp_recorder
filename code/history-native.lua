-- Adapt the native history's data source, not its renderer. The existing rows,
-- portraits, scroll bar, hover card and results transition remain game-owned.
local native=require('code/native')
local binary=require('code/binary-memory')
local stats=require('code/battle-statistics')
local tr=require('code/locale').text
local M={}

function M.verify()
  local sites=assert(require('code/history-sites')[native.profile.name])
  for _,name in ipairs({'prepareList','prepare','action','frame','helpText'}) do
    require('code/hook-check').verify(sites[name],'Battle history conflicts at '..name)
  end
  for _,site in ipairs(sites.operands) do require('code/hook-check').verify(site,'Battle history data conflicts') end
  return sites
end

function M.new(ui,recorder,browser,rename)
  local sites=require('code/history-sites')[native.profile.name]
  local o=setmetatable({ui=ui,recorder=recorder,browser=browser,sites=sites,
    model=require('code/battle-history').new(sites)},{__index=M})
  -- Our catalogue owns sorting/filtering. Retain native resource preparation,
  -- but remove its list-sort call: it rewrites stored trail names and uses the
  -- fixed 250-entry index. Hook only the following position-independent prologue;
  -- UCP hookCode does not relocate stolen relative CALL instructions.
  core.writeCode(sites.prepareList.address,{0x90,0x90,0x90,0x90,0x90})
  -- This one native hint describes immediate entry/right-click deletion, neither
  -- of which belongs to this catalogue. Preserve the callee's seven-argument cleanup.
  core.writeCode(sites.helpText.address,{0x83,0xc4,0x1c,0x90,0x90})
  local originalPrepare
  originalPrepare=core.hookCode(function()
    -- Results return through this same preparation function. Keep the lobby's
    -- mode, rather than saving the temporary results-screen mode on that return.
    if not o.detail then o.lobbyMode=core.readInteger(native.addr(0x191d768)+0x618) end
    originalPrepare()
    core.writeInteger(sites.savedMode,o.lobbyMode)
    o.detail=false; o:refresh()
  end,sites.prepare.address,0,0,#sites.prepare.bytes)
  local originalAction
  originalAction=core.hookCode(function(action)
    if action>=0 and action<8 then
      if browser.preparation then return end
      local selected=o.model.items[core.readInteger(sites.scroll)+action+1]
      if not selected then return end
      if o.model.selected~=selected then o.model.selected=selected; return end
      o.detail=true
    elseif action==11 and browser.preparation then
      browser:cancelPreparation()
    elseif action>=20 and action<=23 then
      o.model:sort(action-19); core.writeInteger(sites.scroll,0); o:publish(); return
    elseif action>=20 then return end -- no filtering or deletion
    return originalAction(action)
  end,sites.action.address,1,0,#sites.action.bytes)
  o.back=function() originalAction(11) end
  local function visible()
    return recorder.mode=='none' and ui:activeDialog()==-1
  end
  local function hasReplay() return o.model.selected and o.model.selected.manifest~=nil end
  local function renameAction() if hasReplay() then rename(o.model:title(),function(name) o.model:rename(name); o:publish() end) end end
  local items={
    {x=270,y=540,width=180,height=30,frontEnd=true,
      visible=hasReplay,action=renameAction,
      label=function() return tr('Rename replay...') end},
    {x=620,y=484,width=170,height=96,frontEnd=true,
      visible=hasReplay,
      action=function() o:play() end,
      render=function(x,y)
        local item=o.model.selected
        local ready=item and item.manifest and item.manifest.status=='complete' and not browser.preparation
        ui:sprite(150,71,x,y-67)
        ui:text(tr(ready and 'Watch replay' or 'Replay unavailable'),x+85,y+68,1,18,false,170,not ready)
      end},
    {x=260,y=514,width=430,height=16,frontEnd=true,enabled=false,
      render=function(x,y) if o.message then ui:text(tr(o.message),x,y,0,18,false,430) end end},
  }
  for row=0,7 do
    local offset=row
    items[#items+1]={x=24,y=132+47*row,width=730,height=47,frontEnd=true,enabled=false,
      visible=function() return o.model.selected~=nil and
        o.model.items[core.readInteger(sites.scroll)+offset+1]==o.model.selected end,
      render=function(x,y) ui:border(x,y,730,47) end}
  end
  ui:attachOverlay({58},items,function()
    local view=core.readInteger(native.addr(0x1fe7d1c))
    return visible() and view==58
  end)
  ui.onNativeKey=function(message,key)
    local view=core.readInteger(native.addr(0x1fe7d1c))
    if visible() and view==58 and message==0x100 and key==113 then
      renameAction(); return true
    end
  end
  return o
end

function M:publish()
  local items=self.model.items
  local records=core.allocate(math.max(1,#items)*stats.SIZE+1,true)
  local indices=core.allocate(math.max(1,#items)*4,true)
  local previous={}
  local ok,reason=pcall(function()
    for index,item in ipairs(items) do
      binary.write(records+(index-1)*stats.SIZE,self.model:display(item))
      core.writeInteger(indices+(index-1)*4,index-1)
    end
    for _,site in ipairs(self.sites.operands) do
      previous[#previous+1]={address=site.address+site.offset,value=core.readInteger(site.address+site.offset)}
      core.writeCodeInteger(site.address+site.offset,(site.kind=='records' and records or indices)+site.delta)
    end
  end)
  if not ok then
    -- Never free storage while even one native operand could still point to it.
    for _,old in ipairs(previous) do core.writeCodeInteger(old.address,old.value) end
    core.deallocate(records); core.deallocate(indices); error(reason)
  end
  if self.records then core.deallocate(self.records); core.deallocate(self.indices) end
  self.records=records; self.indices=indices
  core.writeInteger(self.sites.count,#items)
  core.writeInteger(self.sites.scroll,math.min(core.readInteger(self.sites.scroll),math.max(0,#items-8)))
  core.writeInteger(self.sites.sort,self.model.sortColumn)
end

function M:refresh()
  self.model:refresh(); self:publish()
  local ffi=modules.cffi:cffi()
  local menu=ffi.tonumber(ffi.cast('unsigned long',modules.ui:access().manager.lookupMenu(58)))
  local array=core.readInteger(menu)
  for index=0,4095 do
    local address=array+index*80
    if core.readInteger(address)==0x66 then return end
    local action=core.readInteger(address+24)
    if action>=30 and action<=47 and core.readInteger(address+20)==0 then
      local kind=core.readInteger(address)
      if kind>=0 then core.writeInteger(address,kind-2147483648) end
    end
  end
  error('Battle history menu has no terminator')
end

function M:play()
  local item=self.model.selected
  if not item or not item.manifest or item.manifest.status~='complete' or self.browser.preparation then return end
  self.browser:refresh(item.id)
  self.browser:play(true)
  self.message=self.browser.message
end

function M:advance()
  if not self.browser.preparation then return end
  if core.readInteger(native.addr(0x1fe7d1c))~=58 then self.browser:cancelPreparation() end
  if self.browser:advancePreparation(function()
    -- Native snapshot loading needs the lobby mode, but preparation does not.
    -- Leave history only once verification succeeds and playback is committed.
    self.back(); self.detail=false
  end) then self.ui:close()
  elseif not self.browser.preparation then
    self.message=self.browser.message
  else self.message=self.browser.message
  end
end
return M
