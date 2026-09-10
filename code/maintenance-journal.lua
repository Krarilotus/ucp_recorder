-- Sparse inputs between clock steps, indexed by actual command execution.
local validation=require('code/validation')
local M={PROFILE='native-extra-work-v1',FILE='maintenance.jsonl'}

function M.validate(event,manifest)
  assert(type(event)=='table','Invalid recorded unclocked work')
  validation.integer(event.time,manifest.startTick,manifest.lastTick,'unclocked work tick')
  validation.integer(event.commands,0,manifest.commandCount,'unclocked work command boundary')
  validation.integer(event.kind,1,2,'unclocked work kind')
  validation.integer(event.count,1,2147483647,'unclocked work count')
  return event
end
function M.write(session,kind,count)
  if count==0 then return end
  assert(session.phaseFile and session.status=='recording','No active maintenance journal')
  assert(session.phaseFile:write(json:encode({time=session.engine:tick(),
    commands=session.manifest.commandCount,kind=kind,count=count})..'\n'))
  assert(session.phaseFile:flush())
end
function M.capture(session)
  if session.phaseNative and session.status=='recording' and session.active then
    M.write(session,1,session.phaseNative:take())
  end
end
local function peek(session)
  if session.workEnded then return end
  if not session.nextWork then
    local line=session.phaseFile:read()
    if line then session.nextWork=M.validate(json:decode(line),session.manifest)
    else session.workEnded=true end
  end
  return session.nextWork
end
function M.play(session)
  if not session.manifest.phaseProfile then return end
  assert(session.phaseNative and session.phaseFile,'Missing native work playback adapter')
  local now,executed=session.engine:tick(),session.engine.journal.executed
  while true do
    local event=peek(session)
    if not event then return end
    assert(event.time>=now and event.commands>=executed,'Replay missed an unclocked work boundary')
    if event.time>now or event.commands>executed then return end
    session.phaseNative:replay(event.kind,event.count)
    session.nextWork=nil
  end
end
function M.finished(session)
  if session.manifest.phaseProfile then assert(not peek(session),'Replay ended before its recorded unclocked work') end
end

-- Seal only work up to the last observed boundary; a named copy never edits
-- the source capture. Native state after that boundary belongs to later ticks.
function M.seal(manifest,path,replace)
  if not manifest.phaseProfile then return end
  local filename=path..'/'..M.FILE
  local input=assert(io.open(filename,'rb'))
  local output,reason=io.open(filename..'.tmp','wb')
  if not output then input:close(); error(reason) end
  local ok,err=xpcall(function()
    for line in input:lines() do
      local event=json:decode(line)
      assert(type(event)=='table','Invalid recorded unclocked work')
      validation.integer(event.time,manifest.startTick,2147483647,'unclocked work tick')
      if event.time<=manifest.lastTick then
        M.validate(event,manifest)
        assert(output:write(line..'\n'))
      end
    end
  end,debug.traceback)
  local a,b=input:close(),output:close()
  assert(ok and a and b,err or 'Cannot seal unclocked work journal')
  replace(filename..'.tmp',filename)
  manifest.phaseHash=require('code/native-hash').file(filename,1024*1024*1024)
end
function M.preflight(manifest,path,scan,progress)
  if not manifest.phaseProfile then return end
  local time,commands=manifest.startTick,0
  scan(path..'/'..M.FILE,manifest.phaseHash,function(event)
    M.validate(event,manifest)
    assert(event.time>=time and event.commands>=commands,'Unclocked work is out of execution order')
    time,commands=event.time,event.commands
  end,progress)
end
return M
