local store=require('code/sessions')
local native=require('code/native')
local tr=require('code/locale').text
local Browser={PAGE_SIZE=6}

function Browser:new(recorder)
  return setmetatable({recorder=recorder,items={},index=1,message='Choose a recording.'},{__index=self})
end

function Browser:refresh(preferred)
  local previous=self.items[self.index]
  if self.recorder.lastCompletedReplay~=self.lastCompletedReplay then
    self.lastCompletedReplay=self.recorder.lastCompletedReplay
    preferred=preferred or self.lastCompletedReplay
  end
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
  if self.preparation then return end
  self.lastClick=nil
  self.selected=nil
  if #self.items==0 then self.index=1; self.message='New Skirmishes are recorded automatically when enabled.'; return end
  self.index=math.max(1,math.min(#self.items,index))
  local item=self.items[self.index]
  local ok,manifest=pcall(store.load,item.id,native.profile)
  self.selected=ok and manifest or nil
  if not ok then self.message=tostring(manifest):match('^[^\n]+'):gsub('^.-:%d+: ','')
  elseif store.compatible(manifest) then self.message='Ready to play with your current settings.'
  else
    local checked,readiness=pcall(require('code/launch-readiness').check,manifest)
    self.message=checked and (readiness.ready and 'Play will queue a restart with the recorded settings.'
      or readiness.message) or tostring(readiness):match('^[^\n]+'):gsub('^.-:%d+: ','')
    if checked and readiness.ready and store.settings().hash==(manifest.restartSettingsHash or manifest.settingsHash) then
      self.message='Install the recorded extension and framework versions to play.'
    end
  end
end

-- Native load-list behavior: the same row twice within 500 ms activates it.
-- The clock is presentation-only and never participates in replay scheduling.
function Browser:click(index,now)
  local item=self.items[index]
  if not item then return false end
  local previous=self.lastClick
  self:select(index)
  self.lastClick={id=item.id,time=now}
  return previous and previous.id==item.id and (now-previous.time)%4294967296<500 or false
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
  local name=store.title(item)
  if #name>28 then name=name:sub(1,25)..'...' end
  local label=state=='complete' and (item.sourceId and 'Snapshot' or 'Full match')
    or state=='failed' and 'Failed' or state=='recording' and 'Recording' or 'Incomplete'
  return tr('%s  |  %d ticks  |  %s',name,ticks,tr(label))
end

function Browser:remove()
  assert(self.recorder.mode=='none','Finish the active session before removing a replay')
  local item=assert(self.items[self.index],'Choose a recording.')
  local index=self.index
  store.remove(item.id)
  self:refresh(); self:select(index)
  self.message='Replay removed.'
end

function Browser:play(deferred)
  if self.preparation then return false end
  assert(self.selected,'Choose a completed recording')
  assert(self.recorder.mode=='none','Finish or cancel the active recording first')
  if not store.compatible(self.selected) then self:restart(); return false end
  if deferred then
    local id=self.selected.id
    self.preparation=require('code/preparation-task').new(function(progress)
      return self.recorder:preparePlayback(id,nil,progress)
    end,require('code/platform').milliseconds)
    self.message='Checking replay data...'
    return false
  end
  return self.recorder:guard(function() self.recorder:startPlayback(self.selected.id) end)
end

function Browser:cancelPreparation()
  if self.preparation then self.preparation:cancel() end
end

function Browser:advancePreparation(beforeStart)
  local task=self.preparation
  if not task then return false end
  task:step()
  self.message=task.message or self.message
  if task.status=='pending' then return false end
  print(string.format('[recorder] Replay preparation %s: %.0f ms elapsed, %.0f ms working',
    task.status,task.elapsedMs,task.workMs))
  self.preparation=nil
  if task.status=='cancelled' then self.message='Replay preparation cancelled.'; return false end
  if task.status=='failed' then
    self.message=task.error
    print('[recorder] Replay preparation failed: '..task.error)
    return false
  end
  local ready=task.result
  local ok=self.recorder:guard(function()
    if beforeStart then beforeStart() end
    self.recorder:startPlayback(ready.manifest.id,nil,ready)
  end)
  if not ok then self.message=self.recorder.error end
  return ok
end

function Browser:rename(name)
  assert(self.selected,'Choose a completed recording')
  local id=self.selected.id
  store.rename(id,name,native.profile)
  self:refresh(id)
  self.message='Replay name saved.'
end

function Browser:restart()
  assert(self.selected,'Choose a completed recording')
  assert(self.recorder.mode=='none','Finish or cancel the active recording first')
  if store.settings().hash==(self.selected.restartSettingsHash or self.selected.settingsHash) then
    require('code/launch-readiness').requireReady(self.selected)
    error('Installed extensions or framework differ. Install the recorded versions before playing.')
  end
  require('code/restart').queue(self.selected.id)
  self.message='Restart queued. Exit the game to reopen with recorded settings.'
end

return Browser
