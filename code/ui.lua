local native=require('code/native')
local NativeUI=require('code/native-ui')
local Browser=require('code/browser')
local M={}

function M.createButtons(recorder,sites)
  local browser=Browser:new(recorder)
  local ui=NativeUI.new(sites,function(reason)
    browser.message=tostring(reason):match('^[^\n]+'):gsub('^.-:%d+: ','')
    print('Replay menu: '..tostring(reason))
  end)
  M.browser=browser
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
  button(466,376,190,'Queue settings restart',function() browser:restart() end)
  local dialog=ui:modal(items,#items,680,440,function(x,y)
    ui:text('Recorded Skirmishes',x+24,y+22)
    ui:text(native.profile.name..'  |  '..#browser.items..' recordings',x+24,y+46)
    local item=browser.items[browser.index]
    ui:text(item and ('Selected: '..item.id) or 'Record your next match from the Skirmish lobby.',x+24,y+310)
    ui:text(browser.message,x+24,y+336)
  end)

  -- Extend only the original Skirmish menu's item array, retaining its sentinel.
  local originalSize,itemSize=0x1d10,NativeUI.ITEM_SIZE
  local array=core.allocate(originalSize+2*itemSize,true)
  core.copyMemory(array,native.addr(0x5e9848),originalSize)
  local record=array+originalSize-itemSize
  local browse=record+itemSize
  core.copyMemory(browse+itemSize,record,itemSize)
  ui:button(record,250,550,145,30,function()
    return recorder.status=='armed' and 'Cancel recording' or 'Record next match'
  end,function()
    if recorder.mode=='none' then recorder:guard(function() recorder:startRecording() end)
    elseif recorder.mode=='record' then recorder:guard(function() recorder:stopRecording() end) end
  end,function() return recorder.status=='armed' end)
  ui:button(browse,410,550,145,30,'Replays',function()
    browser:refresh(); ui:show(dialog)
  end)
  core.writeCode(native.addr(0x59ab30),{
    core.AssemblyLambda('push array',{array=array})
  })
end

function M.resetButtons() end -- Labels derive from session state at render time.
return M
