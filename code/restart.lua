local platform=require('code/platform')
local store=require('code/sessions')
local native=require('code/native')
local M={queued=false}

-- Windows CRT argument quoting; no shell interprets this command line.
function M.quote(value)
  assert(type(value)=='string' and not value:find('[%z\r\n]'),'Invalid restart argument')
  value=value:gsub('(\\*)"',function(slashes) return slashes..slashes..'\\"' end)
  value=value:gsub('(\\+)$',function(slashes) return slashes..slashes end)
  return '"'..value..'"'
end

function M.queue(id)
  assert(not M.queued,'A restart is already waiting for the game to close')
  local manifest=store.load(id,native.profile)
  store.preflight(manifest)
  local identity=platform.identity()
  store.write(store.ROOT..'/restart-helper.ps1',require('code/restart-script'))
  store.write(store.ROOT..'/restart-request.json',json:encode({
    id=manifest.id,executable=identity.executable,processId=identity.processId}))
  local powershell=assert(os.getenv('SystemRoot'),'Windows system directory is unavailable')..
    '\\System32\\WindowsPowerShell\\v1.0\\powershell.exe'
  local args=M.quote(powershell)..' -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File '..
    M.quote(store.ROOT..'/restart-helper.ps1')
  platform.spawnHidden(powershell,args)
  M.queued=true
end

return M
