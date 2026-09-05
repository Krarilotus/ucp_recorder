-- A fixed helper program: replay metadata is read as JSON, never evaluated as code.
-- It waits for the current game to exit so two games do not compete for the renderer.
return [=[
$ErrorActionPreference = 'Stop'
$requestPath = Join-Path (Get-Location).Path 'ucp/replays/restart-request.json'
try {
    $request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $gameRoot = [IO.Path]::GetFullPath((Get-Location).Path)
    if ($request.id -notmatch '^[A-Za-z0-9_-]{1,79}$') { throw 'Invalid replay identifier' }
    $sessionPath = Join-Path $gameRoot ('ucp/replays/' + $request.id)
    $settingsPath = Join-Path $sessionPath 'ucp-config.yml'
    $manifestPath = Join-Path $sessionPath 'manifest.json'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.id -ne $request.id -or $manifest.status -ne 'complete') { throw 'Replay is incomplete' }
    $executable = [IO.Path]::GetFullPath($request.executable)
    if ([IO.Path]::GetDirectoryName($executable) -ne $gameRoot) { throw 'Game directory differs' }
    if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $manifest.executable) { throw 'Game executable differs' }
    $gameProcess = Get-Process -Id $request.processId -ErrorAction SilentlyContinue
    if ($null -ne $gameProcess) {
        if ($gameProcess.Path -ne $executable) { throw 'Process identity differs' }
        $gameProcess.WaitForExit()
    }
    if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $manifest.executable) { throw 'Game executable changed while waiting' }
    if ((Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash -ne $manifest.settingsHash) { throw 'Recorded settings are damaged' }
    $env:UCP_RECORDER_REPLAY = $request.id
    # A Windows file path cannot contain a quote. This one ends in .yml, not a backslash.
    $arguments = '--ucp-config-file="' + $settingsPath + '"'
    Start-Process -FilePath $executable -WorkingDirectory $gameRoot -ArgumentList $arguments
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path (Get-Location).Path 'ucp/replays/restart-error.txt')
    exit 1
}
]=]
