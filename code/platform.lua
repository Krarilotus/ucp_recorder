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
local wrap=M.stdcallAddress

-- UCP's library loader accepts extension DLLs, not Windows system libraries.
-- Bootstrap GetProcAddress from the already loaded kernel32 export directory;
-- use the game's verified GetModuleHandleA import (ASLR-resolved by Windows).
local getModule,getProc
local function bootstrap()
  local profile=require('code/native').profile.name
  local imports={SHC=0x59e128,Extreme=0x59e12c}
  getModule=wrap(core.readInteger(assert(imports[profile],'Unknown Windows import profile')),1)
  local function exported(library,name,depth)
    assert(depth<8,'Cyclic Windows export forwarder')
    local base=getModule(buffer('library',library))%4294967296
    assert(base~=0,'Windows library is not loaded: '..library)
    local function u32(a) return core.readInteger(a)%4294967296 end
    local function u16(a) return core.readSmallInteger(a)%65536 end
    assert(u16(base)==0x5a4d,'Invalid Windows library header')
    local pe=base+u32(base+0x3c)
    assert(u32(pe)==0x4550 and u16(pe+24)==0x10b,'Expected PE32 Windows library')
    local start,size=u32(pe+120),u32(pe+124)
    local exports=base+start
    local count=u32(exports+24)
    assert(start>0 and count<65536,'Invalid Windows exports')
    local names,ordinals,functions=base+u32(exports+32),base+u32(exports+36),base+u32(exports+28)
    local function cstring(a)
      local chars={}
      for i=0,255 do
        local byte=core.readByte(a+i)
        if byte==0 then return table.concat(chars) end
        chars[#chars+1]=string.char(byte)
      end
      error('Windows export name is too long')
    end
    for i=0,count-1 do
      if cstring(base+u32(names+i*4))==name then
        local ordinal=u16(ordinals+i*2)
        assert(ordinal<u32(exports+20),'Invalid Windows export ordinal')
        local rva=u32(functions+ordinal*4)
        assert(rva~=0,'Missing Windows export address')
        if rva>=start and rva<start+size then
          local dll,symbol=cstring(base+rva):match('^([^%.]+)%.(.+)$')
          assert(dll and symbol:sub(1,1)~='#','Unsupported Windows export forwarder')
          return exported(dll..'.dll',symbol,depth+1)
        end
        return base+rva
      end
    end
    error('Windows export not found: '..name)
  end
  getProc=wrap(exported('kernel32.dll','GetProcAddress',0),2)
end
function M.stdcall(library,name,count)
  assert(library=='kernel32.dll','Unsupported recorder system library')
  if not getProc then bootstrap() end
  local handle=getModule(buffer('library',library))
  local address=getProc(handle,buffer('symbol',name))
  assert(address~=0,'Windows function is unavailable: '..name)
  return wrap(address,count)
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
