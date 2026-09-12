-- Optional diagnostics consume completed simulation states through this API.
-- They receive copied values, never Recorder's mutable session or engine.
local M={}
local function copy(value)
  if type(value)~='table' then return value end
  local result={};for key,item in pairs(value) do result[key]=copy(item) end
  return result
end
function M.new()
  local callbacks,serial={},0
  local api={}
  function api:register(callback)
    assert(type(callback)=='function','A tick observer must be a function')
    local count=0;for _ in pairs(callbacks) do count=count+1 end
    assert(count<16,'Too many tick observers')
    serial=serial+1;callbacks[serial]=callback;return serial
  end
  function api:remove(token) callbacks[token]=nil end
  function api:dispatch(recorder)
    if next(callbacks)==nil then return end
    local ok,context=pcall(function()
      local singlePlayer=recorder.engine:singlePlayer()
      local active=singlePlayer and recorder.active and recorder.status=='recording'
      local manifest=recorder.manifest or {}
      return {active=not not active,status=recorder.status,singlePlayer=singlePlayer,
        tick=recorder.engine:tick(),resources=active and recorder.engine:resourceState() or {},
        manifest={id=manifest.id,variant=manifest.variant,snapshotHash=manifest.snapshotHash,
          settingsHash=manifest.settingsHash,environmentHash=manifest.environmentHash}}
    end)
    if not ok then print('Tick observers skipped: '..tostring(context));return end
    local tokens={};for token in pairs(callbacks) do tokens[#tokens+1]=token end;table.sort(tokens)
    for _,token in ipairs(tokens) do
      local callback=callbacks[token]
      if callback then
        local success,reason=pcall(callback,copy(context))
        if not success then callbacks[token]=nil;print('Tick observer stopped: '..tostring(reason)) end
      end
    end
  end
  return api
end
return M
