-- Protocol owns the native scheduler, ring and command context.
local M={}
function M.bind(sites)
  local owner=modules and modules.protocol
  assert(owner and type(owner.getNativeCommandInterface)=='function',
    'Recorder requires Protocol 1.1.3 native command interface')
  local value=owner:getNativeCommandInterface()
  assert(value and value.version==1 and value.stride==1272 and value.capacity==200
    and type(value.scheduleCommand)=='function','Recorder does not support this native command interface')
  for _,key in ipairs({'handler','ring','writeIndex','currentCommand','localPlayer','tick','receivedParameters'}) do
    require('code/validation').integer(value[key],0x10000,0x7fffffff,'Protocol '..key)
  end
  assert(value.ring==value.handler+0x3c67c and value.currentCommand==value.handler+0x2d824
    and value.receivedParameters==value.handler+0xcdc
    and value.writeIndex>value.handler and value.writeIndex<value.handler+0x200000,
    'Recorder requires the verified native command-buffer layout')
  local result={}
  for key,item in pairs(sites) do result[key]=item end
  result.commands=value
  result.writeIndexOffset=value.writeIndex-value.handler
  return result
end
return M
