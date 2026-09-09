-- Presentation only: the existing view owns player choice; the recorder owns
-- validation and stopping. Viewer speed belongs to the shared playback controls;
-- neither the strip nor keyboard handling dispatches gameplay commands.
local tr=require('code/locale').text
local M={}

function M.new(recorder,view)
  return setmetatable({recorder=recorder,view=view,
    controls=require('code/playback-controls').new(recorder)},{__index=M})
end

function M:status()
  local r=self.recorder
  if r.status=='error' then return tostring(r.error or tr('Playback failed.')) end
  if r.status=='finished' then return tr('Playback finished.') end
  if r.engine:isPaused() then return tr('Playback paused.') end
  return tr('Checks matching')
end

function M:progress()
  local r=self.recorder
  local first,last=r.manifest.startTick,r.manifest.lastTick
  return tr('Replay: %d / %d ticks',math.max(0,math.min(r.engine:tick(),last)-first),last-first)
end

-- Native RenderPlayerAvatars uses 72x72 images. Reserve the native bottom
-- controls and metadata above; wrap the strip into columns on shorter windows.
function M.portraitPosition(index,height)
  local rows=math.max(1,math.floor((height-160-180+8)/80))
  return 10+math.floor((index-1)/rows)*80,160+((index-1)%rows)*80
end

function M:install(ui)
  local items={}
  for index=1,8 do
    local row=index
    items[#items+1]={x=10,y=160,width=72,height=72,
      position=function(_,height) return M.portraitPosition(row,height) end,
      visible=function() return self.view:players()[row]~=nil end,
      action=function() local slot=self.view:players()[row]; if slot then self.view:select(slot) end end,
      render=function(x,y)
        local slot=self.view:players()[row]
        if not slot then return end
        ui.avatarNative(slot,x,y)
        if slot==self.view:player() then ui:border(x-2,y-2,76,76) end
      end}
  end
  items[#items+1]={x=-410,y=12,width=398,height=58,enabled=false,
    render=function(x,y)
      ui:hudText(self:progress(),x+398,y,-1,398)
      ui:hudText(self:status(),x+398,y+18,-1,398)
      ui:hudText(tr('F3: replay information'),x+398,y+36,-1,398)
    end}
  items[#items+1]={x=54,y=12,width=320,height=180,enabled=false,
    visible=function() return self.details and self.recorder.playbackInfo~=nil end,
    render=function(x,y)
      if self.info~=self.recorder.playbackInfo then
        self.info=self.recorder.playbackInfo
        self.lines=require('code/playback-info').lines(self.recorder.manifest,self.info)
      end
      for index,line in ipairs(self.lines) do ui:hudText(line,x,y+(index-1)*18,0,320) end
    end}
  for _,direction in ipairs({-1,1}) do
    local step=direction
    items[#items+1]={x=step==-1 and -230 or -48,y=76,width=36,height=28,
      label=step==-1 and '-' or '+',
      visible=function() return self.recorder.status~='finished' end,
      enabled=function() return self.controls:available() end,
      action=function() self.controls:stepSpeed(step) end}
  end
  items[#items+1]={x=-190,y=76,width=138,height=28,enabled=false,
    visible=function() return self.recorder.status~='finished' end,
    render=function(x,y)
      local speed=self.controls:speed()
      ui:hudText(tr('Speed: %d',math.min(speed,1000))..(speed>=1100 and '+' or ''),x+132,y+6,-1,132)
    end}
  items[#items+1]={x=-180,y=76,width=168,height=28,label=function() return tr('Statistics') end,
    visible=function() return self.recorder.status=='finished' and self.recorder.manifest
      and self.recorder.manifest.battle~=nil end,
    action=function() self.showStatistics() end}
  ui:attachOverlay({14,16},items,function() return self.view:available() and ui:activeDialog()==-1 end,true)
end

function M:key(message,key)
  if self.view:available() and self.controls:key(message,key) then return true end
  if key~=114 then return false end -- F3, presentation only
  if message==0x101 then self.keyDown=false; return self.view:available() end
  if message~=0x100 or not self.view:available() then return false end
  if not self.keyDown then self.details=not self.details end
  self.keyDown=true
  return true
end

return M
