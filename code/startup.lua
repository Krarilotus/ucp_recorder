-- A small support report, independent of native hooks and replay file creation.
-- Do not dump option values, account information or configuration file contents.
local M={REPORT='ucp/recorder-startup.txt'}

function M.run(callback)
  local lines={'UCP Recorder startup', 'UTC: '..os.date('!%Y-%m-%dT%H:%M:%SZ'),
    'Loaded extensions in order:'}
  for i,extension in ipairs(allActiveExtensions or {}) do
    lines[#lines+1]=string.format('%d. %s %s',i,tostring(extension.name),tostring(extension.version))
  end
  local stage='initialization'
  local ok,result=xpcall(function()
    return callback(function(name,action)
      stage=name
      local value=action()
      lines[#lines+1]='OK: '..name
      return value
    end)
  end,debug.traceback)
  local profile=require('code/native').profile
  lines[#lines+1]='Native profile: '..(profile and profile.name or 'unidentified')
  lines[#lines+1]=ok and 'READY: replay hooks and menus installed; gameplay not validated.'
    or ('FAILED: '..stage..'\n'..tostring(result))
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
    error('Recorder startup failed during '..stage..'. See '..M.REPORT..
      ' or ucp3.log.\n'..tostring(result),0)
  end
  return result
end
return M
