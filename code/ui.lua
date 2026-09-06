local native=require('code/native')
local NativeUI=require('code/native-ui')
local Browser=require('code/browser')
local M={}

function M.createButtons(recorder,sites)
  local browser=Browser:new(recorder)
  local editor,editorAction,editorBack,nameDialog
  local function short(reason) return tostring(reason):match('^[^\n]+'):gsub('^.-:%d+: ','') end
  local ui=NativeUI.new(sites,function(reason)
    browser.message=short(reason)
    print('Replay menu: '..tostring(reason))
  end)
  M.browser=browser
  local function cancelName() editor=nil; ui:show(editorBack) end
  local function saveName()
    local ok,reason=pcall(editorAction,editor.value)
    if ok then editor=nil; ui:show(reason or editorBack)
    else browser.message=short(reason) end
  end
  local function openName(value,action,back)
    editor=require('code/name-editor').new(value)
    editorAction=action; editorBack=back
    browser.message='Type a name. Enter saves; Escape cancels.'
    ui:show(nameDialog)
  end
  nameDialog=ui:modal({
    {x=24,y=72,width=552,height=36,label=function() return editor and editor:label() or '' end,
      action=function() if editor then editor.selected=true end end,selected=function() return true end},
    {x=24,y=166,width=130,height=30,label='Cancel',action=cancelName},
    {x=446,y=166,width=130,height=30,label='Save name',action=saveName},
  },3,600,240,function(x,y)
    ui:text('Save replay as...',x+24,y+24)
    ui:text(browser.message:sub(1,65),x+24,y+124)
  end)
  ui:installInput(function() return recorder.engine:singlePlayer() end,function(message,key)
    if ui:activeDialog()==nameDialog and editor then
      local action=editor:input(message,key)
      if action=='save' then saveName() elseif action=='cancel' then cancelName() end
    elseif message==0x102 and key==27 then
      if ui:activeDialog()==M.statusDialog then ui:show(5) else ui:close() end
    end
  end)
  ui:extendPause(function()
    return recorder.status=='recording' and 'Save replay as...' or 'Replay status'
  end,function()
    if recorder.status=='recording' and recorder.observedTick then
      openName(require('code/sessions').title(recorder.manifest),function(name)
        local copy=recorder:saveCopy(name)
        browser.message='Saved: '..require('code/sessions').title(copy)
        return M.statusDialog
      end,5)
    else
      browser.message=recorder.error and short(recorder.error)
        or ('Replay '..recorder.status..'. Leave the mission to return to the library.')
      ui:show(M.statusDialog)
    end
  end,function() return recorder.engine:singlePlayer() and (recorder.mode~='none' or recorder.status=='error') end)
  M.statusDialog=ui:modal({
    {x=24,y=130,width=150,height=30,label='Back',action=function() ui:show(5) end}
  },1,600,200,function(x,y)
    ui:text('Replay status',x+24,y+24)
    ui:text(browser.message:sub(1,70),x+24,y+70)
    if recorder.status=='recording' then ui:text('Automatic recording continues until you leave the match.',x+24,y+98) end
  end)
  local dialog
  local items={}
  local function button(x,y,width,label,action,selected)
    items[#items+1]={x=x,y=y,width=width,height=30,label=label,action=action,selected=selected}
  end
  for row=0,Browser.PAGE_SIZE-1 do
    local offset=row
    button(24,76+row*36,632,function() return browser:row(browser:firstRow()+offset) end,
      function() browser:select(browser:firstRow()+offset) end,
      function() return browser.index==browser:firstRow()+offset end)
  end
  button(24,376,86,'Previous',function() browser:page(-1) end)
  button(114,376,62,'Next',function() browser:page(1) end)
  button(180,376,80,'Refresh',function() browser:refresh() end)
  button(274,376,66,'Close',function() ui:close() end)
  button(364,376,90,'Play',function()
    if browser:play() then ui:close()
    elseif recorder.error then browser.message=recorder.error:match('^[^\n]+'):gsub('^.-:%d+: ','') end
  end)
  button(466,376,190,'Rename replay...',function()
    assert(browser.selected,'Choose a completed recording')
    openName(require('code/sessions').title(browser.selected),function(name) browser:rename(name) end,dialog)
  end)
  dialog=ui:modal(items,#items,680,440,function(x,y)
    ui:text('Recorded Skirmishes',x+24,y+22)
    ui:text(native.profile.name..'  |  '..#browser.items..' recordings',x+24,y+46)
    local item=browser.items[browser.index]
    ui:text(item and ('Selected: '..require('code/sessions').title(item))
      or 'New Skirmishes are recorded automatically when enabled.',x+24,y+310)
    ui:text(browser.message:sub(1,78),x+24,y+336)
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
    return recorder.autoRecord and 'Auto: on' or 'Auto: off'
  end,function()
    if not recorder.engine:singlePlayer() then return end
    if recorder.mode=='play' or recorder.active then return end
    recorder.autoRecord=not recorder.autoRecord
    if not recorder.autoRecord and recorder.status=='armed' then recorder:guard(function() recorder:reset() end) end
  end,function() return recorder.autoRecord end)
  ui:button(browse,350,550,90,30,'Replays',function()
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
