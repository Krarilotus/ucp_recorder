-- Validate persisted input before native loading, with bounded memory. Playback
-- already streams commands; preparation must not retain a second complete copy.
local validation=require('code/validation')
local digest=require('code/native-hash')
local M={MAX_STREAM=1024*1024*1024,MAX_LINE=32768}

local function scan(path,expected,consume,progress)
  local pending=''
  local hash=digest.file(path,M.MAX_STREAM,function(chunk)
    local data=pending..chunk
    local offset=1
    while true do
      local newline=data:find('\n',offset,true)
      if not newline then break end
      assert(newline-offset<=M.MAX_LINE,'Replay row is too long')
      local line=data:sub(offset,newline-1):gsub('\r$','')
      if line:find('%S') then consume(json:decode(line)) end
      offset=newline+1
      if progress then progress('Checking replay data...') end
    end
    pending=data:sub(offset)
    assert(#pending<=M.MAX_LINE,'Replay row is too long')
  end)
  assert(hash==expected,'Replay stream is damaged: '..path)
  if pending:find('%S') then consume(json:decode(pending)) end
end

function M.check(manifest,path,progress)
  require('code/maintenance-journal').preflight(manifest,path,scan,progress)
  local count,previous,batchSize=0,manifest.startTick,0
  scan(path..'/stream-commands.json',manifest.commandsHash,function(value)
    local c=validation.sessionCommand(value,manifest)
    assert(c.time>=previous and c.time<=manifest.lastTick,'Replay command tick is outside its ordered timeline')
    batchSize=c.time==previous and batchSize+1 or 1
    assert(batchSize<=100,'Replay exceeds the native 100-command dispatch batch')
    count=count+1; previous=c.time
  end,progress)
  assert(count==manifest.commandCount,'Replay command count differs')
  local verification=require('code/replay-verification')
  local interval=verification.interval(manifest.verificationProfile)
  local tick=math.ceil(manifest.startTick/interval)*interval
  scan(path..'/stream-rng-sync.json',manifest.checkpointsHash,function(checkpoint)
    assert(type(checkpoint)=='table' and checkpoint.time==tick and tick<=manifest.lastTick,'Invalid replay checkpoint timeline')
    verification.validate(checkpoint,manifest.verificationProfile)
    tick=tick+interval
  end,progress)
  assert(tick>manifest.lastTick,'Replay verification data ended early')
  local info=''
  local hash=digest.file(path..'/stream-infself.json',M.MAX_LINE,function(chunk) info=info..chunk end)
  assert(hash==manifest.infoHash,'Replay info stream is damaged')
  validation.info(json:decode(info))
end
return M
