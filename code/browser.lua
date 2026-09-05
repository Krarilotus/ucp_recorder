local store=require('code/sessions')
local native=require('code/native')
local Browser={PAGE_SIZE=6}

function Browser:new(recorder)
  return setmetatable({recorder=recorder,items={},index=1,message='Choose a recording.'},{__index=self})
end

function Browser:refresh(preferred)
  local previous=self.items[self.index]
  preferred=preferred or (previous and previous.id) or os.getenv('UCP_RECORDER_REPLAY')
  self.items={}
  for _,item in ipairs(store.list()) do
    if item.variant==native.profile.name then self.items[#self.items+1]=item end
  end
  self.index=1
  for i,item in ipairs(self.items) do if item.id==preferred then self.index=i; break end end
  self:select(self.index)
end

function Browser:select(index)
  self.selected=nil
  if #self.items==0 then self.index=1; self.message='No recordings yet. Record a Skirmish first.'; return end
  self.index=math.max(1,math.min(#self.items,index))
  local item=self.items[self.index]
  local ok,manifest=pcall(store.load,item.id,native.profile)
  self.selected=ok and manifest or nil
  if not ok then self.message=tostring(manifest):match('^[^\n]+'):gsub('^.-:%d+: ','')
  elseif store.compatible(manifest) then self.message='Ready to play with your current settings.'
  else self.message='Recorded settings differ. Queue a restart, then exit the game.' end
end

function Browser:page(delta)
  self:select(self.index+delta*self.PAGE_SIZE)
end

function Browser:firstRow()
  return math.floor((self.index-1)/self.PAGE_SIZE)*self.PAGE_SIZE+1
end

function Browser:row(index)
  local item=self.items[index]
  if not item then return '' end
  local ticks=type(item.lastTick)=='number' and type(item.startTick)=='number' and item.lastTick-item.startTick or 0
  if ticks~=ticks or ticks<0 or ticks>2147483647 then ticks=0 end
  ticks=math.floor(ticks)
  local state=type(item.status)=='string' and item.status:sub(1,16) or 'unavailable'
  return string.format('%s  |  %d ticks  |  %s',item.id,ticks,state)
end

function Browser:play()
  assert(self.selected,'Choose a completed recording')
  assert(store.compatible(self.selected),'Restart with the recorded settings before playing')
  assert(self.recorder.mode=='none','Finish or cancel the active recording first')
  return self.recorder:guard(function() self.recorder:startPlayback(self.selected.id) end)
end

function Browser:restart()
  assert(self.selected,'Choose a completed recording')
  assert(self.recorder.mode=='none','Finish or cancel the active recording first')
  require('code/restart').queue(self.selected.id)
  self.message='Restart queued. Exit the game to reopen with recorded settings.'
end

return Browser
