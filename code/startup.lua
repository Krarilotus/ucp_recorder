-- A small support report, independent of native hooks and replay file creation.
-- Do not dump option values, account information or configuration file contents.
local M={REPORT='ucp/recorder-startup.txt'}

---@class RecorderStartupResult
---@field status 'ready'|'disabled'
---@field stage string
---@field reason string|nil

-- Checks must not install recorder hooks. Only install() crosses that boundary;
-- an exception after it starts cannot be recovered without a verified rollback.
---@param callback fun(check: fun(name: string, action: function): any, install: fun(action: function))
---@return RecorderStartupResult
function M.run(callback,clock)
  clock=clock or function() return os.clock()*1000 end
  local started=clock()
  local lines={'UCP Recorder startup', 'UTC: '..os.date('!%Y-%m-%dT%H:%M:%SZ'),
    'Loaded extensions in order:'}
  for i,extension in ipairs(allActiveExtensions or {}) do
    lines[#lines+1]=string.format('%d. %s %s',i,tostring(extension.name),tostring(extension.version))
  end
  local stage='initialization'
  local installing=false
  local ok,result=xpcall(function()
    local function check(name,action)
      assert(not installing,'Recorder checks must precede installation')
      stage=name
      local before=clock()
      local value=action()
      lines[#lines+1]=string.format('OK: %s (%.0f ms)',name,clock()-before)
      return value
    end
    callback(check,function(action)
      assert(not installing,'Recorder installation may only start once')
      installing=true
      stage='hook and menu installation'
      local before=clock()
      action()
      lines[#lines+1]=string.format('OK: %s (%.0f ms)',stage,clock()-before)
    end)
    assert(installing,'Recorder installation was not started')
  end,debug.traceback)
  local profile=require('code/native').profile
  lines[#lines+1]='Native profile: '..(profile and profile.name or 'unidentified')
  lines[#lines+1]=string.format('Recorder startup: %.0f ms',clock()-started)
  lines[#lines+1]=ok and 'READY: replay hooks and menus installed; gameplay not validated.'
    or ((installing and 'FAILED: ' or 'DISABLED: ')..stage..'\n'..tostring(result))
  lines[#lines+1]='Setup and troubleshooting: docs/setup.md in the recorder release ZIP.'
  local report=table.concat(lines,'\n')..'\n'
  print(report)
  -- Reporting failures must never hide the original failure or prevent a launch.
  local written,reason=pcall(function()
    local file=assert(io.open(M.REPORT,'wb'))
    local saved,saveReason=file:write(report)
    local closed,closeReason=file:close()
    assert(saved and closed,tostring(saveReason or closeReason))
  end)
  if not written then print('Recorder startup report could not be saved: '..tostring(reason)) end
  if not ok then
    if installing then
      error('Recorder installation failed. Restart after resolving '..stage..'. See '..M.REPORT..
        ' or ucp3.log.\n'..tostring(result),0)
    end
    -- UCP's ERROR logger displays its existing Windows message box without
    -- terminating the process. Do not silently start a match without recording.
    log(ERROR,'Recorder is disabled for this launch. No replay will be recorded.\n'..
      'The game can continue. Failed check: '..stage..'.\n'..
      'See '..M.REPORT..' or ucp3.log for details.\n'..tostring(result):match('^[^\r\n]*'))
    return {status='disabled',stage=stage,reason=tostring(result)}
  end
  return {status='ready',stage=stage}
end
return M
