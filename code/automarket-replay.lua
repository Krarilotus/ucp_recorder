-- An explicit adapter for the reviewed Automarket 1.1.0 wire format.
-- Weekly trades are deterministic simulation work and must not be injected twice.
local M={SIZE=272}
local function integer(value,lo,hi,label)
  return require('code/validation').integer(value,lo,hi,label)
end

function M.version(name)
  for _,extension in ipairs(allActiveExtensions or {}) do
    if extension.name==name then return extension.version end
  end
end

function M.saveHookAvailable()
  return M.version('map-extensions')=='1.0.0' and modules and modules['map-extensions']~=nil
end

function M.current()
  local versions={}
  for _,extension in ipairs(allActiveExtensions or {}) do versions[extension.name]=extension.version end
  if not versions.automarket then return nil end
  assert(versions.automarket=='1.1.0','Replay adapter requires Automarket 1.1.0')
  assert(versions.protocol=='1.0.0' and versions['map-extensions']=='1.0.0',
    'Automarket replay adapter requires protocol and map-extensions 1.0.0')
  local protocol=assert(modules and modules.protocol,'Automarket replay protocol is unavailable')
  local id=protocol:getProtocolNumber('automarket','commitSingle')
  integer(id,130,2147483647,'Automarket protocol number')
  return {version='1.1.0',protocol=id}
end

function M.descriptor(value)
  if value==nil then return end
  assert(type(value)=='table' and value.version=='1.1.0','Unsupported Automarket replay adapter')
  integer(value.protocol,130,2147483647,'Automarket protocol number')
end

function M.compatible(recorded)
  local ok,current=pcall(M.current)
  if not ok then return false end
  if not recorded or not current then return recorded==current end
  return recorded.version==current.version and recorded.protocol==current.protocol
end

local function word(bytes,offset)
  return bytes[offset+1]+bytes[offset+2]*256+bytes[offset+3]*65536+bytes[offset+4]*16777216
end

function M.command(command,descriptor)
  M.descriptor(descriptor)
  assert(descriptor,'Custom replay command has no Automarket adapter')
  assert(command.size==M.SIZE,'Invalid Automarket replay payload size')
  local bytes=require('code/utils').hexToTable(command.data)
  assert(word(bytes,0)==descriptor.protocol,'Unknown custom replay protocol')
  assert(word(bytes,4)==command.player,'Automarket replay payload belongs to another player')
  integer(word(bytes,268),0,100,'Automarket fee')
  integer(bytes[9],0,1,'Automarket enabled flag')
  for i=17,66 do integer(bytes[i],0,1,'Automarket goods flag') end
end

return M
