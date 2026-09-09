-- Validated, bounded disk access shared by native-world conversion and restore.
local native=require('code/native')
local digest=require('code/native-hash')
local M={}
local Reader={}

local function read(path,limit)
  local file=assert(io.open(path,'rb'),'Missing world file: '..path)
  local ok,data=pcall(function()
    local size=assert(file:seek('end'))
    assert(size<=limit,'World file is too large: '..path)
    assert(file:seek('set',0))
    local raw=assert(file:read('*a'))
    assert(#raw==size,'World file changed while reading: '..path)
    return raw
  end)
  local closed=file:close()
  assert(ok and closed,data or 'Cannot close world file')
  return data
end

---@class RecordedWorldReader
---@field path string
---@field capture table
---@field manifest table
---@field header string
---@field entries NativeWorldSection[]
---@field bytes integer
---@field automarket string|nil
---@return RecordedWorldReader
function M.open(path)
  assert(type(path)=='string' and (path:match('^ucp/multiplayer%-recordings/[%w_-]+$')
    or path:match('^ucp/replays/[%w_-]+$')),
    'Invalid multiplayer capture path')
  local capture=json:decode(read(path..'/capture.json',1024*1024))
  assert(type(capture)=='table' and capture.kind=='multiplayer-capture' and capture.format==1,
    'Unsupported multiplayer capture')
  assert(capture.id==path:match('([^/]+)$'),'Capture folder identity differs')
  assert(capture.variant==native.profile.name and capture.executable==native.profile.sha256,
    'World requires its recorded executable')
  local summary=capture.world
  assert(type(summary)=='table' and summary.status=='complete' and summary.header==true,
    'Capture has no complete native starting header; record a new match')
  local raw=read(path..'/world.json',1024*1024)
  assert(sha.sha256(raw)==summary.hash,'World manifest is damaged')
  local manifest=json:decode(raw)
  assert(type(manifest)=='table' and manifest.format==1 and manifest.status=='complete'
    and manifest.kind=='native-world-evidence' and manifest.tick==capture.startTick
    and manifest.variant==capture.variant and manifest.executable==capture.executable,
    'World identity differs')
  local entries,profile=require('code/world-layout').decode(read(path..'/world-layout.bin',1968),capture.variant)
  assert(manifest.tableHash==profile.hash and manifest.bytes==profile.total
    and type(manifest.sections)=='table' and #manifest.sections==#entries,'World layout differs')
  for i,entry in ipairs(entries) do
    local recorded=manifest.sections[i]
    assert(type(recorded)=='table','Invalid recorded world section')
    for key,value in pairs(entry) do assert(recorded[key]==value,'World section descriptor differs') end
    require('code/validation').hash(recorded.sha256,'world section hash')
    entry.sha256=recorded.sha256
  end
  local header=read(path..'/world-header.bin',2141)
  require('code/world-header').validate(header,manifest.header)
  assert((manifest.automarket~=nil)==(summary.automarket==true),'Automarket world presence differs')
  local market
  local extensions
  assert((manifest.extensions~=nil)==(summary.extensions==true),'Extension world presence differs')
  if manifest.extensions then
    extensions=read(path..'/extensions.zip',require('code/extension-container').MAX_BYTES)
    assert(#extensions==manifest.extensions.bytes and sha.sha256(extensions)==manifest.extensions.sha256,
      'Extension starting state is damaged')
  end
  if manifest.automarket then
    market=read(path..'/automarket.bin',2416)
    local info=manifest.automarket
    require('code/automarket-replay').descriptor(info)
    assert(info.format==2 and info.bytes==2416 and #market==2416 and market:sub(1,4)=='\2\0\0\0'
      and sha.sha256(market)==info.sha256,'Automarket starting state is damaged')
  end
  return setmetatable({path=path,capture=capture,manifest=manifest,header=header,
    entries=entries,bytes=profile.total,automarket=market,extensions=extensions},{__index=Reader})
end

---@param callback fun(entry: NativeWorldSection, data: string)
function Reader:eachSection(callback)
  digest.prepare()
  local file=assert(io.open(self.path..'/world.bin','rb'),'Missing native world')
  local ok,reason=xpcall(function()
    assert(file:seek('end')==self.bytes,'Native world length differs')
    assert(file:seek('set',0))
    for _,entry in ipairs(self.entries) do
      local data=assert(file:read(entry.size))
      assert(#data==entry.size and digest.sha256(data)==entry.sha256,
        'Native world section is damaged: '..entry.section)
      callback(entry,data)
    end
    assert(file:read(1)==nil,'Native world grew while reading')
  end,debug.traceback)
  local closed=file:close()
  assert(ok and closed,reason or 'Cannot close native world')
end
M.read=read
return M
