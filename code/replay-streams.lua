-- Own replay file handles and one prefetched command. Session validation,
-- native buffers, scheduling and RNG state belong to their respective owners.
local Streams={}
local keys={'commands','rng','info'}

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
  for _,field in ipairs({'commandsFile','rngFile','infoFile','tickFile','phaseFile'}) do
    local file=self[field]; self[field]=nil
    if file then
      local ok,closed,reason=pcall(file.close,file)
      if not ok or not closed then failure=failure or reason or closed or 'Cannot close replay file' end
    end
  end
  assert(not failure,tostring(failure))
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
      opened[key..'File']=assert(io.open(path,mode),'Cannot open recording: '..path)
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
