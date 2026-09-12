-- WinProc Handler owns registration and native dispatch. No game entry patch.
local M={}

function M.interface()
  local owner=assert(modules and modules.winProcHandler,'Recorder requires WinProc Handler 1.0.0')
  local interface=owner:cinterface()
  for _,name in ipairs({'RegisterProc','CallNextProc'}) do
    local address=interface[name]
    assert(type(address)=='number' and address>0 and address<4294967296
      and address==math.floor(address),'Invalid WinProc Handler export: '..name)
  end
  return interface
end

function M.install(interface,handler,onError)
  local platform=require('code/platform')
  local nextProc=platform.stdcallAddress(interface.CallNextProc,5)
  local register=platform.stdcallAddress(interface.RegisterProc,2)
  -- RPS's thiscall callback adds an unused ECX before the five stdcall arguments.
  -- It therefore returns with the owner's required ret 20. Patch only this
  -- private callback stub, retaining it for the process lifetime (no unregister).
  local callback=core.allocateCode({0x90,0x90,0x90,0x90,0x90,0xC2,0x14,0})
  local result={callback=callback,nextProc=nextProc}
  local function dispatch(priority,window,message,key,data)
    local consumed,value=handler(window,message,key,data)
    if consumed then return value or 0 end
    return nextProc(priority,window,message,key,data)
  end
  result.original=core.hookCode(function(_,priority,window,message,key,data)
    local ok,value=pcall(dispatch,priority,window,message,key,data)
    if ok then return value end
    -- Never retry uncertain downstream dispatch or unwind into native code.
    pcall(onError,value)
    return 0
  end,callback,6,1,5)
  -- Preserve Recorder's former position near the native handler, after input
  -- remapping and graphics conversion. Forward the actual collision result.
  result.priority=register(callback,100000)
  assert(result.priority~=-2147483648,'Recorder input registration failed')
  return result
end

return M
