-- Map Extensions owns the section table and both extension-aware native entries.
local M={}
function M.interface()
  local owner=modules and modules['map-extensions']
  assert(owner and type(owner.getNativeSaveInterface)=='function',
    'Recorder requires Map Extensions 1.1.4 native save interface')
  local value=owner:getNativeSaveInterface()
  assert(value and value.version==1 and value.sectionCount==122 and value.descriptorSize==16
    and value.readContext==1,
    'Recorder does not support this native save interface layout')
  for _,key in ipairs({'packager','sections','readWorld','writeWorld'}) do
    require('code/validation').integer(value[key],0x10000,0x7fffffff,'Map Extensions '..key)
  end
  require('code/validation').integer(value.resources,0x10000,0x7fffffff-0x7c000,'Map Extensions resources')
  require('code/validation').integer(value.resourceFileName,0x10000,0x7fffffff-20,'Map Extensions resourceFileName')
  assert(type(value.resourceFileNameBytes)=='string' and #value.resourceFileNameBytes==20,
    'Map Extensions native filename context is missing')
  return value
end

function M.bind(sites)
  local owner=M.interface()
  local result={}
  for key,value in pairs(sites) do result[key]=value end
  result.packager=owner.packager
  result.sections=owner.sections
  -- Empty byte guards are deliberate: these are the owner's installed wrapper
  -- entries, not original unpatched functions or Recorder hook sites.
  result.save={address=owner.writeWorld,bytes={}}
  result.readWorld={address=owner.readWorld,bytes={}}
  return result
end
return M
