local native=require('code/native')
local NativeUI=require('code/native-ui')
local Browser=require('code/browser')
local tr=require('code/locale').text
local M={}

function M.createButtons(recorder,sites)
  -- Native report actions 71..79 reject logical pause before opening the book.
  -- A viewer may inspect a frozen/finished replay. Admit only that UI branch;
  -- never clear the world's pause, change its actor or release the tick gate.
  require('code/hook-check').verify(sites.reportPause.guard or sites.reportPause,
    'Recorder UI conflicts at reportPause')
  require('code/fixes').install({sites.reportPause},recorder.playbackActive,
    recorder.engine.base+0x618,nil,recorder.engine.offlineFlag)
  local browser=Browser:new(recorder)
  local editor,editorAction,editorBack,editorTitle,editorError,nameDialog
  local function short(reason) return tostring(reason):match('^[^\n]+'):gsub('^.-:%d+: ','') end
  local ui=NativeUI.new(sites,function(reason)
    browser.message=short(reason)
    print('Replay menu: '..tostring(reason))
  end)
  M.browser=browser
  local view=require('code/replay-view').new(recorder)
  M.view=view
  M.hud=require('code/replay-hud').new(recorder,view)
  M.hud:install(ui)
  ui.renderScope=function(callback)
    local screen=core.readInteger(native.addr(0x1fe7d1c))
    if ui:activeDialog()~=-1 or (screen~=14 and screen~=16) then return callback() end
    local ok,result=pcall(view.render,view,callback)
    if not ok then browser.message=short(result); print('Replay view: '..tostring(result)) end
    return ok and result or nil
  end
  ui:installViewRender()
  local function cancelName()
    editor=nil
    ui:show(editorBack)
  end
  local function saveName()
    local ok,reason=pcall(editorAction,editor.value)
    if ok then editor=nil; ui:show(reason or editorBack)
    else editorError=short(reason) end
  end
  local function openName(value,action,back,title)
    editor=require('code/name-editor').new(value)
    editorAction=action; editorBack=back
    editorTitle=title or 'Save replay'
    editorError=nil
    ui:show(nameDialog)
  end
  nameDialog=ui:modal({
    {x=24,y=40,width=552,height=36,label=function() return editor and editor:label() or '' end,
      action=function() if editor then editor.selected=true end end,selected=function() return true end},
    {x=24,y=126,width=160,height=30,label=function() return tr('Cancel') end,action=cancelName},
    {x=416,y=126,width=160,height=30,label=function() return tr('Save name') end,action=saveName},
  },3,600,180,function(x,y)
    if editorError then ui:text(tr(editorError),x+300,y+90,1,18,false,552) end
  end,function() return tr(editorTitle) end)
  ui:installInput(function()
    return recorder.engine:localSession() or ui:activeDialog()==M.statusDialog or ui:activeDialog()==nameDialog
  end,function(message,key)
    if ui:activeDialog()==nameDialog and editor then
      local action=editor:input(message,key)
      if action=='save' then saveName() elseif action=='cancel' then cancelName() end
    elseif message==0x102 and key==27 then
      if ui:activeDialog()==M.statusDialog then ui:show(5) else ui:close() end
    end
  end)
  ui:extendPause(function()
    if not recorder.engine:localSession() then return tr('Replay status') end
    if recorder.status=='error' then return tr('Replay failed - details') end
    return tr(recorder.status=='recording' and 'Save replay' or 'Replay status')
  end,function()
    if not recorder.engine:localSession() then
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
    return recorder.mode~='play' and (not recorder.engine:localSession() or recorder.mode~='none' or recorder.status=='error')
  end,function() return recorder.mode=='play' end)
  M.statusDialog=ui:modal({
    -- This submenu is opened from the native options menu. That owner already
    -- suspends the world and provides Resume game; Back must not toggle pause.
    {x=24,y=208,width=260,height=30,label=function() return tr('Back') end,
      action=function() ui:show(5) end},
    {x=316,y=208,width=260,height=30,label=function()
      local trace=recorder.engine.trace
      if not recorder.engine:localSession() and trace and trace.file and trace.saveCopy then return tr('Save capture as...') end
      return ''
    end,action=function()
      local trace=recorder.engine.trace
      if not recorder.engine:localSession() and trace and trace.file and trace.saveCopy then
        openName(trace.capture.id,function(name)
          local copy=trace:saveCopy(name)
          browser.message=tr('Saved: %s',copy.displayName)
          return M.statusDialog
        end,M.statusDialog,'Save capture as...')
      end
    end}
  },2,600,262,function(x,y)
    if not recorder.engine:localSession() then
      local lines=recorder.engine.trace and recorder.engine.trace:statusLines()
        or {'Multiplayer replay recording is not available.', 'Test capture is disabled for this launch.'}
      for i,line in ipairs(lines) do ui:text(tr(line),x+24,y+48+i*26,0,18,false,552) end
      return
    end
    local message=browser.message
    ui:text(tr(message),x+24,y+70,0,18,false,552)
    if recorder.status=='error' and recorder.mode=='record' then
      ui:text(tr('Recording stopped. This match is no longer being recorded.'),x+24,y+98)
      ui:text(tr('Resume the game to continue playing normally.'),x+24,y+124)

    end
    if recorder.status=='recording' then ui:text(tr('Automatic recording continues until you leave the match.'),x+24,y+98) end
  end,function() return tr('Replay status') end)
  M.history=require('code/history-native').new(ui,recorder,browser,function(value,action)
    openName(value,action,-1,'Rename replay...')
  end)
  M.hud.showStatistics=function() M.history:showFinishedStatistics() end
  M.hud.controls.input=function(direction) ui.nativeSpeedKey(direction) end
  local historyKey=ui.onNativeKey
  ui.onNativeKey=function(message,key)
    return M.hud:key(message,key) or (historyKey and historyKey(message,key))
  end
  ui.onMenuUpdated=function()
    require('code/snapshot-jobs').poll()
    if recorder.snapshots and recorder.snapshots.requested then
      recorder:guard(function() recorder.snapshots:advance() end)
    else M.history:advance() end
  end

end

function M.resetButtons() end -- Labels derive from session state at render time.
return M
