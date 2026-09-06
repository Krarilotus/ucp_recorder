local native=require('code/native')
local NativeUI=require('code/native-ui')
local Browser=require('code/browser')
local tr=require('code/locale').text
local M={}

function M.createButtons(recorder,sites)
  local browser=Browser:new(recorder)
  local editor,editorAction,editorBack,editorTitle,nameDialog
  local function short(reason) return tostring(reason):match('^[^\n]+'):gsub('^.-:%d+: ','') end
  local ui=NativeUI.new(sites,function(reason)
    browser.message=short(reason)
    print('Replay menu: '..tostring(reason))
  end)
  M.browser=browser
  local view=require('code/replay-view').new(recorder)
  M.view=view
  ui.renderScope=function(callback)
    local screen=core.readInteger(native.addr(0x1fe7d1c))
    if ui:activeDialog()~=-1 or (screen~=14 and screen~=16) then return callback() end
    local ok,result=pcall(view.render,view,callback)
    if not ok then browser.message=short(result); print('Replay view: '..tostring(result)) end
    return ok and result or nil
  end
  ui:installViewRender()
  local dialog,removeDialog,playerDialog
  local renameSelected,removeSelected,playSelected
  local function cancelName()
    editor=nil
    if editorBack==dialog then browser:select(browser.index) end
    ui:show(editorBack)
  end
  local function saveName()
    local ok,reason=pcall(editorAction,editor.value)
    if ok then editor=nil; ui:show(reason or editorBack)
    else browser.message=short(reason) end
  end
  local function openName(value,action,back,title)
    editor=require('code/name-editor').new(value)
    editorAction=action; editorBack=back
    editorTitle=title or 'Save replay as...'
    browser.message='Type a name. Enter saves; Escape cancels.'
    ui:show(nameDialog)
  end
  nameDialog=ui:modal({
    {x=24,y=72,width=552,height=36,label=function() return editor and editor:label() or '' end,
      action=function() if editor then editor.selected=true end end,selected=function() return true end},
    {x=24,y=166,width=160,height=30,label=function() return tr('Cancel') end,action=cancelName},
    {x=416,y=166,width=160,height=30,label=function() return tr('Save name') end,action=saveName},
  },3,600,240,function(x,y)
    ui:text(tr(editorTitle),x+300,y+24,1,16)
    ui:text(tr(browser.message),x+300,y+124,1,18,false,552)
  end)
  ui:installInput(function()
    return recorder.engine:singlePlayer() or ui:activeDialog()==M.statusDialog
  end,function(message,key)
    if ui:activeDialog()==nameDialog and editor then
      local action=editor:input(message,key)
      if action=='save' then saveName() elseif action=='cancel' then cancelName() end
    elseif ui:activeDialog()==dialog then
      if message==0x100 then
        if key==38 then browser:select(browser.index-1)
        elseif key==40 then browser:select(browser.index+1)
        elseif key==33 then browser:page(-1)
        elseif key==34 then browser:page(1)
        elseif key==36 then browser:select(1)
        elseif key==35 then browser:select(#browser.items)
        elseif key==113 then renameSelected()
        elseif key==46 then removeSelected() end
      elseif message==0x102 then
        if key==13 then playSelected() elseif key==27 then ui:close() end
      end
    elseif message==0x102 and key==27 then
      if ui:activeDialog()==removeDialog then ui:show(dialog)
      elseif ui:activeDialog()==playerDialog then ui:show(M.statusDialog)
      elseif ui:activeDialog()==M.statusDialog then ui:show(5) else ui:close() end
    end
  end)
  ui:extendPause(function()
    if not recorder.engine:singlePlayer() then return tr('Replay status') end
    if recorder.status=='error' then return tr('Replay failed - details') end
    if recorder.mode=='play' then return tr('Replay controls') end
    return tr(recorder.status=='recording' and 'Save replay as...' or 'Replay status')
  end,function()
    if not recorder.engine:singlePlayer() then
      ui:show(M.statusDialog)
    elseif recorder.status=='recording' and recorder.observedTick then
      openName(require('code/sessions').title(recorder.manifest),function(name)
        local copy=recorder:saveCopy(name)
        browser.message=tr('Saved: %s',require('code/sessions').title(copy))
        return M.statusDialog
      end,5)
    else
      browser.message=recorder.error and short(recorder.error)
        or tr('Replay %s. Leave the mission to return to the library.',recorder.status)
      ui:show(M.statusDialog)
    end
  end,function()
    return not recorder.engine:singlePlayer() or recorder.mode~='none' or recorder.status=='error'
  end)
  M.statusDialog=ui:modal({
    {x=24,y=186,width=180,height=30,label=function() return tr('Back') end,action=function() ui:show(5) end},
    {x=340,y=186,width=236,height=30,label=function() return view:available() and tr('View player') or '' end,
      action=function() if view:available() then ui:show(playerDialog) end end}
  },2,600,240,function(x,y)
    ui:text(tr(recorder.mode=='play' and 'Replay controls' or 'Replay status'),x+300,y+24,1,16)
    if not recorder.engine:singlePlayer() then
      local lines=recorder.engine.trace and recorder.engine.trace:statusLines()
        or {'Multiplayer replay recording is not available.', 'Test capture is disabled for this launch.'}
      for i,line in ipairs(lines) do ui:text(tr(line):sub(1,80),x+24,y+48+i*26) end
      return
    end
    local message=browser.message
    if recorder.mode=='play' and recorder.status~='error' then
      message=recorder.status=='finished' and 'Playback finished.' or 'Playback running.'
    end
    ui:text(tr(message),x+24,y+70,0,18,false,552)
    if recorder.status=='error' and recorder.mode=='record' then
      ui:text(tr('Recording stopped. This match is no longer being recorded.'),x+24,y+98)
      ui:text(tr('Resume the game to continue playing normally.'),x+24,y+124)
    elseif recorder.status=='error' and recorder.mode=='play' then
      ui:text(tr('Playback failed. Leave the mission to return to the library.'),x+24,y+98)
    end
    if recorder.status=='recording' then ui:text(tr('Automatic recording continues until you leave the match.'),x+24,y+98) end
    if view:available() then ui:text(tr('Viewing: player %d',view:player()),x+24,y+150) end
  end)
  local players={}
  for index=1,8 do
    local row=index
    players[#players+1]={x=24+((row-1)%2)*280,y=74+math.floor((row-1)/2)*38,width=272,height=30,
      label=function() local slot=view:players()[row]; return slot and tr('Player %d',slot) or '' end,
      selected=function() return view:players()[row]==view:player() end,
      action=function() local slot=view:players()[row]; if slot then view:select(slot); ui:show(5) end end}
  end
  players[#players+1]={x=24,y=280,width=180,height=30,label=function() return tr('Back') end,
    action=function() ui:show(M.statusDialog) end}
  playerDialog=ui:modal(players,#players,600,334,function(x,y)
    ui:text(tr('View player'),x+300,y+24,1,16)
    ui:text(tr('Viewing does not change recorded actions.'),x+300,y+240,1)
  end)
  removeDialog=ui:modal({
    {x=24,y=172,width=180,height=30,label=function() return tr('Cancel') end,action=function() ui:show(dialog) end},
    {x=396,y=172,width=180,height=30,label=function() return tr('Remove') end,action=function()
      browser:remove(); ui:show(dialog)
    end}
  },2,600,238,function(x,y)
    ui:text(tr('Remove replay?'),x+300,y+24,1,16)
    local item=browser.items[browser.index]
    ui:text(item and require('code/sessions').title(item) or '',x+300,y+80,1)
    ui:text(tr('The files are kept in ucp/replays/removed.'),x+300,y+120,1)
  end)
  renameSelected=function()
    if not browser.selected then return end
    openName(require('code/sessions').title(browser.selected),function(name) browser:rename(name) end,dialog,'Rename replay...')
  end
  removeSelected=function() if browser.items[browser.index] then ui:show(removeDialog) end end
  playSelected=function()
    if not browser.selected then return end
    if browser:play() then ui:close()
    elseif recorder.error then browser.message=short(recorder.error) end
  end
  local items={}
  local function button(x,y,width,label,action,selected,leftAligned,enabled)
    items[#items+1]={x=x,y=y,width=width,height=30,label=label,action=action,selected=selected,leftAligned=leftAligned,enabled=enabled}
  end
  for row=0,Browser.PAGE_SIZE-1 do
    local offset=row
    button(24,76+row*40,632,function() return browser:row(browser:firstRow()+offset) end,
      function()
        if browser:click(browser:firstRow()+offset,require('code/platform').milliseconds()) then playSelected() end
      end,
      function() return browser.index==browser:firstRow()+offset end,true)
  end
  button(24,352,40,function() return browser:firstRow()>1 and '<' or '' end,
    function() if browser:firstRow()>1 then browser:page(-1) end end)
  button(616,352,40,function() return browser:firstRow()+Browser.PAGE_SIZE<=#browser.items and '>' or '' end,
    function() if browser:firstRow()+Browser.PAGE_SIZE<=#browser.items then browser:page(1) end end)
  button(24,434,140,function() return tr('Back') end,function() ui:close() end)
  button(188,434,140,function() return tr('Remove') end,removeSelected,nil,nil,
    function() return browser.items[browser.index]~=nil and recorder.mode=='none' end)
  button(352,434,140,function() return tr('Rename replay...') end,renameSelected,nil,nil,
    function() return browser.selected~=nil end)
  button(516,434,140,function() return tr('Play') end,playSelected,nil,nil,
    function() return browser.selected~=nil and recorder.mode=='none' end)
  dialog=ui:modal(items,#items,680,496,function(x,y)
    ui:text(tr('Recorded Skirmishes'),x+340,y+22,1,16)
    ui:text(native.profile.name..'  |  '..tr('%d recordings',#browser.items),x+340,y+50,1)
    ui:text(tr(browser.message),x+340,y+320,1,18,false,632)
    if #browser.items>Browser.PAGE_SIZE then
      ui:text(tr('Page %d / %d',math.floor((browser.index-1)/Browser.PAGE_SIZE)+1,
        math.ceil(#browser.items/Browser.PAGE_SIZE)),x+340,y+360,1)
    end
    ui:text(tr('Enter: play   F2: rename   Delete: remove'),x+340,y+398,1,19)
  end)

  -- Extend only the original Skirmish menu's item array, retaining its sentinel.
  local originalSize,itemSize=0x1d10,NativeUI.ITEM_SIZE
  local array=core.allocate(originalSize+2*itemSize,true)
  core.copyMemory(array,native.addr(0x5e9848),originalSize)
  local record=array+originalSize-itemSize
  local browse=record+itemSize
  core.copyMemory(browse+itemSize,record,itemSize)
  -- The native bottom-row sprites occupy x=10..190, 300..345,
  -- 444..489 and 520..800 (including transparent hit-box portions).
  ui:button(record,195,550,100,30,function()
    return tr(recorder.autoRecord and 'Auto: on' or 'Auto: off')
  end,function()
    if not recorder.engine:singlePlayer() then return end
    if recorder.mode=='play' or recorder.active then return end
    recorder.autoRecord=not recorder.autoRecord
    if not recorder.autoRecord and recorder.status=='armed' then recorder:guard(function() recorder:reset() end) end
  end,function() return recorder.autoRecord end)
  ui:button(browse,350,550,90,30,function() return tr('Replays') end,function()
    if not recorder.engine:singlePlayer() then return end
    browser:refresh(); ui:show(dialog)
  end)
  core.writeCode(native.addr(0x59ab30),{
    core.AssemblyLambda('push array',{array=array})
  })
  ui:trackVisibility({record,browse},function() return recorder.engine:singlePlayer() end)
end

function M.resetButtons() end -- Labels derive from session state at render time.
return M
