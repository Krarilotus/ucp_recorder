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

local mkdir, getError
function M.mkdir(path)
  mkdir = mkdir or M.stdcall('kernel32.dll', 'CreateDirectoryA', 2)
  getError = getError or M.stdcall('kernel32.dll','GetLastError',0)
  if mkdir(buffer('directory',path),0)~=0 then return true end
  local reason=getError()
  assert(reason==183,'Cannot create replay directory (Windows error '..reason..')')
  return false
end

local move
function M.replace(source, destination)
  move = move or M.stdcall('kernel32.dll', 'MoveFileExA', 3)
  local a,b=buffer('source',source),buffer('destination',destination)
  assert(move(a, b, 9) ~= 0, 'Cannot finish writing replay metadata')
end

return M
