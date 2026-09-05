-- Track native ring ownership separately from the ring's reusable state byte.
local validation=require('code/validation')
local M={}
function M.new() return setmetatable({slots={},nextSequence=1,executed=0},{__index=M}) end

function M:queue(slot,command)
  validation.command(command)
  validation.integer(slot,0,199,'command ring slot')
  assert(not self.slots[slot],'Replay command slot reused before execution')
  local copy={}; for k,v in pairs(command) do copy[k]=v end
  self.slots[slot]={command=copy,sequence=self.nextSequence}
  self.nextSequence=self.nextSequence+1
end

function M:before(slot,actual)
  local entry=assert(self.slots[slot],'Unexpected native command during playback')
  assert(entry.sequence==self.executed+1,'Native replay command execution order differs')
  for _,key in ipairs({'commandCategory','time','player','size'}) do
    assert(actual[key]==entry.command[key],'Native replay command '..key..' differs')
  end
  assert(actual.data:upper()==entry.command.data:upper(),'Native replay command payload differs')
  return entry
end

-- Ring indices wrap; they are not the recorded execution order. Build a whole
-- due batch before publishing any entries to the native dispatcher.
function M:select(now)
  local entries={}
  for slot,entry in pairs(self.slots) do
    assert(entry.command.time>=now,'Replay command missed its simulation tick')
    if entry.command.time==now then entries[#entries+1]={slot=slot,entry=entry} end
  end
  table.sort(entries,function(a,b) return a.entry.sequence<b.entry.sequence end)
  assert(#entries<=100,'Replay exceeds the native 100-command dispatch batch')
  for i,item in ipairs(entries) do
    assert(item.entry.sequence==self.executed+i,'Replay due batch has a missing or reordered command')
  end
  return entries
end

function M:after(slot,entry)
  assert(entry and self.slots[slot]==entry,'Native replay command ownership changed during execution')
  self.slots[slot]=nil
  self.executed=self.executed+1
end

function M:pending() return next(self.slots)~=nil end
return M
