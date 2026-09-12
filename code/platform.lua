-- Small Win32 adapter; stdcall is wrapped explicitly because RPS exposeCode
-- supports cdecl/thiscall, not stdcall. No shell command construction is used.
local M = {}
local buffers = {}
local function buffer(key,value)
  assert(type(value)=='string' and #value<4096 and not value:find('\0',1,true),'Invalid replay path')
  buffers[key]=buffers[key] or core.allocate(4096,true)
  core.writeString(buffers[key],value..'\0')
  return buffers[key]
end
function M.stdcallAddress(address,count)
  local code = {0x55, 0x8B, 0xEC} -- push ebp; mov ebp,esp
  for i = count, 1, -1 do
    code[#code+1] = 0xFF; code[#code+1] = 0x75; code[#code+1] = 4+i*4
  end
  code[#code+1] = core.callTo(address)
  code[#code+1] = 0x5D; code[#code+1] = 0xC3
  local target=core.allocateCode(core.calculateCodeSize(code))
  core.writeCode(target,code)
  return core.exposeCode(target,count,0)
end
-- RPS owns Windows library loading and export/forwarder resolution. Its
-- exposeCode still needs the stdcall bridge above on the supported runtime.
local functions={}
function M.stdcall(library,name,count)
  assert(library=='kernel32.dll' or library=='advapi32.dll' or library=='winmm.dll',
    'Unsupported recorder system library')
  assert(type(name)=='string' and name:match('^[%w_]+$'),'Invalid Windows symbol')
  assert(type(count)=='number' and count>=0 and count<=10 and count==math.floor(count),
    'Invalid Windows argument count')
  local key=library..'/'..name
  local existing=functions[key]
  if existing then
    assert(existing.count==count,'Conflicting Windows function ABI: '..name)
    return existing.call
  end
  local address=ucp.internal.getLibraryProcAddressA(library,name)
  assert(type(address)=='number' and address%4294967296~=0,'Missing Windows function: '..name)
  local call=M.stdcallAddress(address,count)
  functions[key]={count=count,call=call}
  return call
end

local tickCount
function M.milliseconds()
  tickCount=tickCount or M.stdcall('kernel32.dll','GetTickCount',0)
  return tickCount()%4294967296
end

-- Native save/history presentation clock, independent of simulation ticks.
local multimediaClock
function M.multimediaMilliseconds()
  multimediaClock=multimediaClock or M.stdcall('winmm.dll','timeGetTime',0)
  return multimediaClock()%4294967296
end

local mkdir, getAttributes
function M.mkdir(path)
  mkdir = mkdir or M.stdcall('kernel32.dll', 'CreateDirectoryA', 2)
  getAttributes = getAttributes or M.stdcall('kernel32.dll','GetFileAttributesA',1)
  local address=buffer('directory',path)
  if mkdir(address,0)~=0 then return true end
  -- Do not carry GetLastError across Lua/RPS calls: intervening runtime work may
  -- change it. An existing directory is the only non-error false result.
  local attributes=getAttributes(address)
  assert(attributes>=0 and attributes~=0xffffffff and math.floor(attributes/16)%2==1,
    'Cannot create replay directory: '..path)
  return false
end

local move
function M.replace(source, destination)
  move = move or M.stdcall('kernel32.dll', 'MoveFileExA', 3)
  local a,b=buffer('source',source),buffer('destination',destination)
  assert(move(a, b, 9) ~= 0, 'Cannot finish writing replay metadata')
end

-- Removing a replay is a recoverable, non-overwriting directory rename. Never
-- recurse through files or follow a reparse point supplied in the replay folder.
function M.removeReplay(root,id,restore)
  assert(root=='ucp/replays' and type(id)=='string' and #id<80 and id:match('^[%w_-]+$'),
    'Invalid replay removal path')
  getAttributes=getAttributes or M.stdcall('kernel32.dll','GetFileAttributesA',1)
  local function directory(path)
    local value=getAttributes(buffer('directory',path))
    assert(value>=0 and value~=0xffffffff and math.floor(value/16)%2==1
      and math.floor(value/1024)%2==0,'Replay directory is missing or is a link')
  end
  directory(root)
  M.mkdir(root..'/removed'); directory(root..'/removed')
  directory(root..(restore and '/removed/' or '/')..id)
  local full=M.stdcall('kernel32.dll','GetFullPathNameA',4)
  local function absolute(path)
    local input=buffer('fullInput',path); local output=buffer('fullOutput','')
    local size=full(input,4096,output,0)
    assert(size>0 and size<4096,'Cannot resolve replay removal path')
    return core.readString(output,size):gsub('/','\\')
  end
  local base=absolute(root)
  local source,destination=absolute(root..'/'..id),absolute(root..'/removed/'..id)
  assert(source:lower()==(base..'\\'..id):lower()
    and destination:lower()==(base..'\\removed\\'..id):lower(),'Replay removal escaped its directory')
  if restore then source,destination=destination,source end
  move=move or M.stdcall('kernel32.dll','MoveFileExA',3)
  assert(move(buffer('source',source),buffer('destination',destination),8)~=0,
    'Cannot remove replay; a removed copy may already exist')
end

function M.identity()
  local getModule=M.stdcall('kernel32.dll','GetModuleFileNameW',3)
  local getPID=M.stdcall('kernel32.dll','GetCurrentProcessId',0)
  local toUTF8=M.stdcall('kernel32.dll','WideCharToMultiByte',8)
  local wide=core.allocate(8192,true)
  local count=getModule(0,wide,4096)
  assert(count>0 and count<4096,'Cannot identify the running game')
  local path=buffer('executable','')
  local bytes=toUTF8(65001,0,wide,count,path,4096,0,0)
  assert(bytes>0,'Cannot encode the game executable path')
  return {executable=core.readString(path,bytes),processId=getPID()}
end

local openLease,closeLease
-- A share-denied, delete-on-close lease lives exactly as long as its native
-- handle. A failed open means leave that owner's cache alone, for any reason.
function M.tryTemporaryLease(path)
  openLease=openLease or M.stdcall('kernel32.dll','CreateFileA',7)
  closeLease=closeLease or M.stdcall('kernel32.dll','CloseHandle',1)
  local handle=openLease(buffer('cache-lease',path),0xC0000000,0,0,4,0x04000100,0)
  if handle==-1 or handle==4294967295 or handle==0 then return end
  return function()
    if handle then assert(closeLease(handle)~=0,'Cannot close snapshot cache lease'); handle=nil end
  end
end

function M.spawnHidden(executable,commandLine)
  local create=M.stdcall('kernel32.dll','CreateProcessW',10)
  local toWide=M.stdcall('kernel32.dll','MultiByteToWideChar',6)
  local close=M.stdcall('kernel32.dll','CloseHandle',1)
  local function wide(key,text)
    local utf8=buffer(key,text)
    local result=core.allocate(8192,true)
    assert(toWide(65001,8,utf8,-1,result,4096)>0,'Cannot encode restart command')
    return result
  end
  local startup,process=core.allocate(68,true),core.allocate(16,true)
  core.writeInteger(startup,68)
  local ok=create(wide('helper-executable',executable),wide('helper-command',commandLine),
    0,0,0,0x08000000,0,0,startup,process)
  assert(ok~=0,'Cannot start the replay restart helper')
  close(core.readInteger(process)); close(core.readInteger(process+4))
end

return M
