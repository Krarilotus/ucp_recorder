-- Own replay file handles and one prefetched command. Session validation,
-- native buffers, scheduling and RNG state belong to their respective owners.
local Streams={}
local keys={'commands','rng','info'}
local streamFields={'commandsFile','rngFile','infoFile','tickFile','phaseFile'}

function Streams:new(params)
  local self=setmetatable({mode='none'},{__index=self})
  self:setName(params.name)
  return self
end

function Streams:setName(name)
  self.name=name
  self.commandsFileName=name..'-commands.json'
  self.rngFileName=name..'-rng-sync.json'
  self.infoFileName=name..'-infself.json'
end

function Streams:closeFiles()
  local failure
  for _,field in ipairs(streamFields) do
    local file=self[field]; self[field]=nil
    if file then
      local ok,closed,reason=pcall(file.close,file)
      if not ok or not closed then failure=failure or reason or closed or 'Cannot close replay file' end
    end
  end
  assert(not failure,tostring(failure))
end

-- A file position alone loses a command or maintenance event already prefetched
-- by its reader. Keep both in one bookmark; native world state is owned elsewhere.
function Streams:bookmark()
  local positions={}
  for _,field in ipairs(streamFields) do
    if self[field] then positions[field]=assert(self[field]:seek(),'Cannot bookmark replay stream') end
  end
  return {positions=positions,nextCommand=self.nextCommand,nextWork=self.nextWork,workEnded=self.workEnded}
end

function Streams.validateBookmark(bookmark,opened)
  assert(type(bookmark)=='table' and type(bookmark.positions)=='table',
    'Invalid replay stream bookmark')
  -- Validate every stream before moving any cursor. Journals use binary I/O:
  -- CRT text cookies change when a later suffix is trimmed during sealing.
  local integer=require('code/validation').integer
  for key in pairs(bookmark.positions) do
    local known=false; for _,field in ipairs(streamFields) do if key==field then known=true end end
    assert(known,'Unknown replay stream in bookmark')
  end
  for _,field in ipairs(streamFields) do
    local offset=bookmark.positions[field]
    assert((opened[field]~=nil)==(offset~=nil),'Replay bookmark stream set differs')
    if offset~=nil then integer(offset,0,1073741824,'stream position') end
  end
end

function Streams:restoreBookmark(bookmark)
  assert(self.mode=='play','Bookmark restoration requires playback')
  Streams.validateBookmark(bookmark,self)
  for _,field in ipairs(streamFields) do
    if self[field] then
      assert(self[field]:seek('set',bookmark.positions[field])==bookmark.positions[field],
        'Cannot restore replay stream position')
    end
  end
  self.nextCommand=bookmark.nextCommand; self.nextWork=bookmark.nextWork; self.workEnded=bookmark.workEnded
end

function Streams:reset()
  self.mode='none'; self.nextCommand=nil
  self:closeFiles()
end

-- Commit handles only after all opens succeed. Preflight belongs to sessions;
-- repeating it here would read and decode an entire recording a second time.
function Streams:openFiles(mode)
  assert(self.mode=='none','A replay session is already active')
  assert(mode=='r' or mode=='w','Invalid replay stream mode')
  local opened,created={},{}
  local ok,reason=pcall(function()
    if mode=='w' then
      for _,key in ipairs(keys) do
        local path=self[key..'FileName']; local existing=io.open(path,'r')
        if existing then existing:close(); error('Cannot overwrite recording: '..path) end
      end
    end
    for _,key in ipairs(keys) do
      local path=self[key..'FileName']
      opened[key..'File']=assert(io.open(path,mode..'b'),'Cannot open recording: '..path)
      if mode=='w' then created[#created+1]=path end
    end
  end)
  if not ok then
    for _,file in pairs(opened) do pcall(file.close,file) end
    for _,path in ipairs(created) do os.remove(path) end
    error(reason)
  end
  self.nextCommand=nil
  for key,file in pairs(opened) do self[key]=file end
end

function Streams:saveInfo(gameType,mapSeed,matchSeed,RNGvalue1,RNGvalue2,RNGindex1,RNGindex2)
  assert(self.infoFile:write(json:encode({gameType=gameType,mapSeed=mapSeed,matchSeed=matchSeed,
    RNGvalue1=RNGvalue1,RNGvalue2=RNGvalue2,RNGindex1=RNGindex1,RNGindex2=RNGindex2})..'\n'))
  assert(self.infoFile:flush())
end

function Streams:peekCommand()
  if not self.nextCommand then
    local line=self.commandsFile:read()
    self.nextCommand=line and json:decode(line) or nil
  end
  return self.nextCommand
end

function Streams:consumeSavedCommand()
  local command=self:peekCommand(); self.nextCommand=nil
  return command
end
return Streams
