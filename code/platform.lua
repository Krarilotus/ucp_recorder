-- Small Win32 adapter; stdcall is wrapped explicitly because RPS exposeCode
-- supports cdecl/thiscall, not stdcall. No shell command construction is used.
local M = {}
local libraries = {}
local buffers = {}
local function buffer(key,value)
  assert(type(value)=='string' and #value<4096 and not value:find('\0',1,true),'Invalid replay path')
  buffers[key]=buffers[key] or core.allocate(4096,true)
  core.writeString(buffers[key],value)
  return buffers[key]
end
function M.stdcall(library, name, count)
  if not libraries[library] then libraries[library] = assert(core.openLibraryHandle(library)) end
  local address = assert(libraries[library]:getProcAddress(name))
  local code = {0x55, 0x8B, 0xEC} -- push ebp; mov ebp,esp
  for i = count, 1, -1 do
    code[#code+1] = 0xFF; code[#code+1] = 0x75; code[#code+1] = 4+i*4
  end
  code[#code+1] = core.callTo(address)
  code[#code+1] = 0x5D; code[#code+1] = 0xC3
  return core.exposeCode(core.allocateCode(code), count, 0)
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
