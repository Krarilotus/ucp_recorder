-- The save owner supplies only callbacks registered as read-only capture.
-- Keep their bytes in the existing extension ZIP and native load pipeline.
local M={}

function M.owner()
  local version=require('code/automarket-replay').version('map-extensions')
  if version~='1.1.0' then return nil end
  local owner=assert(modules and modules['map-extensions'],'Required state owner is unavailable')
  assert(type(owner.requiredStateVersion)=='function' and owner:requiredStateVersion()==1
    and type(owner.captureRequiredSections)=='function' and type(owner.requiredStateIntegrity)=='function'
    and type(owner.requiredStateContracts)=='function','Unsupported required state capture API')
  return owner
end

function M.capture(entries)
  local owner=M.owner()
  if not owner then return false end
  local captured=owner:captureRequiredSections()
  assert(type(captured)=='table','Required state capture did not return entries')
  for name,data in pairs(captured) do
    assert(entries[name]==nil,'Duplicate required state entry: '..tostring(name))
    entries[name]=data
  end
  return true
end

function M.integrity()
  local owner=M.owner()
  return owner and owner:requiredStateIntegrity() or nil
end

function M.observeBoundary()
  local owner=M.owner()
  if not owner then return end
  assert(type(owner.observeRequiredStateBoundary)=='function'
    and type(owner.requiredStateBoundaryIntegrity)=='function','Missing required state boundary API')
  owner:observeRequiredStateBoundary()
end

function M.boundaryIntegrity()
  local owner=M.owner()
  return owner and owner:requiredStateBoundaryIntegrity() or nil
end

function M.validate(expected)
  local owner=M.owner()
  local contracts=owner and owner:requiredStateContracts() or {}
  if expected==nil then
    assert(next(contracts)==nil,'Replay has no required extension state checkpoints')
    return
  end
  assert(type(expected)=='table','Invalid required extension state checkpoint')
  local count=0
  for name,value in pairs(expected) do
    count=count+1
    assert(count<=256 and type(name)=='string' and type(value)=='table','Invalid extension state checkpoint')
    local contract=contracts[name]
    assert(contract and contract.format==value.format and contract.fingerprint==value.fingerprint,
      'Recorded extension state contract differs: '..name)
    assert(type(value.digest)=='string' and #value.digest>0 and #value.digest<=256
      and value.digest:match('^[%w_.-]+$'),'Invalid extension state digest')
  end
  for name in pairs(contracts) do assert(expected[name],'Missing extension state checkpoint: '..name) end
end

function M.check(expected)
  M.validate(expected)
  if expected==nil then return end
  local actual=M.integrity() or {}
  for name,value in pairs(expected) do
    assert(actual[name] and actual[name].digest==value.digest,'Extension state divergence: '..name)
  end
end

return M
