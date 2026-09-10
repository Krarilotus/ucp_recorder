-- One optional frozen world at a time. A nonblocking menu-frame poll publishes
-- completed compression; closing a viewer cancels without freeing worker memory.
local platform=require('code/platform')
local storage=require('code/snapshot-store')
local digest=require('code/native-hash')
local M={}
local active,lastPoll
local Job={}

function M.start(engine,path,month,commands,bookmark,complete)
  if active then return nil,'busy' end
  local started=platform.milliseconds()
  local tick,random,resources=engine:tick(),engine:rngData(),engine:resourceData()
  local point={profile=storage.PROFILE,tick=tick,month=month,commands=commands,bookmark=bookmark,
    rngHash=digest.sha256(random),stateHash=digest.sha256(random..resources)}
  local ok,reader=pcall(require('code/world-capture').freeze,engine)
  local unchanged=engine:tick()==tick and engine:rngData()==random and engine:resourceData()==resources
  if not ok then assert(unchanged,'Snapshot capture changed simulation state'); return nil,tostring(reader) end
  active=setmetatable({reader=reader,path=path,point=point,random=random,complete=complete,
    started=started,freezeMilliseconds=(platform.milliseconds()-started)%4294967296},{__index=Job})
  if not unchanged then active:cancel(); error('Snapshot capture changed simulation state') end
  lastPoll=nil
  return active
end

function Job:cancel()
  self.cancelled=true; self.reader:cancel()
end

function M.poll()
  if not active then return end
  local now=platform.milliseconds()
  if lastPoll and (now-lastPoll)%4294967296<100 then return end
  lastPoll=now
  local job=active
  if not job.reader:ready() then return end
  local began=platform.milliseconds()
  local ok,reason=true,nil
  if not job.cancelled then
    ok,reason=pcall(function()
      local encoded=job.reader:write(job.path..'.sav.tmp')
      storage.publish(job.path,job.point,job.random,encoded)
    end)
  end
  -- Only a completed worker can release its source and output allocations.
  job.reader:close(); active=nil
  if job.cancelled then return end
  if not ok then
    os.remove(job.path..'.sav.tmp'); os.remove(job.path..'.rng.tmp'); storage.remove(job.path)
    job.complete(nil,tostring(reason)); return
  end
  print(string.format('[recorder] Snapshot at tick %d: %d bytes; freeze %d ms; publish %d ms; elapsed %d ms',
    job.point.tick,job.point.bytes,job.freezeMilliseconds,(platform.milliseconds()-began)%4294967296,
    (platform.milliseconds()-job.started)%4294967296))
  job.complete(job.point)
end
return M
