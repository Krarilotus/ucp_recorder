-- A fixed helper program: replay metadata is read as JSON, never evaluated as code.
-- It waits for the current game to exit so two games do not compete for the renderer.
return [=[
$ErrorActionPreference = 'Stop'
function Get-ReplayHash {
    param([string]$Path)
    # Get-FileHash is a script module and may be absent from an inherited
    # PowerShell 7 module path when this Windows PowerShell 5 helper starts.
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [IO.File]::OpenRead($Path)
        return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '')
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $algorithm.Dispose()
    }
}
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
    $settingsHash = $manifest.settingsHash
    if ($null -ne $manifest.settingsCapture -or $null -ne $manifest.restartSettingsHash) {
        if ($manifest.settingsCapture -ne 'resolved-v1' -or $manifest.restartSettingsHash -notmatch '^[0-9a-fA-F]{64}$') {
            throw 'Invalid recorded launch settings profile'
        }
        $settingsPath = Join-Path $sessionPath 'replay-config.yml'
        $settingsHash = $manifest.restartSettingsHash
    }
    $executable = [IO.Path]::GetFullPath($request.executable)
    if ([IO.Path]::GetDirectoryName($executable) -ne $gameRoot) { throw 'Game directory differs' }
    if ((Get-ReplayHash $executable) -ne $manifest.executable) { throw 'Game executable differs' }
    $gameProcess = Get-Process -Id $request.processId -ErrorAction SilentlyContinue
    if ($null -ne $gameProcess) {
        if ($gameProcess.Path -ne $executable) { throw 'Process identity differs' }
        $gameProcess.WaitForExit()
    }
    if ((Get-ReplayHash $executable) -ne $manifest.executable) { throw 'Game executable changed while waiting' }
    if ((Get-ReplayHash (Join-Path $sessionPath 'ucp-config.yml')) -ne $manifest.settingsHash) { throw 'Recorded settings are damaged' }
    if ((Get-ReplayHash $settingsPath) -ne $settingsHash) { throw 'Recorded launch settings are damaged' }
    if ($manifest.settingsCapture -eq 'resolved-v1') {
        if ((Get-ReplayHash (Join-Path $sessionPath 'environment.json')) -ne $manifest.environmentHash) {
            throw 'Recorded environment is damaged'
        }
    }
    $env:UCP_RECORDER_REPLAY = $request.id
    # A Windows file path cannot contain a quote. This one ends in .yml, not a backslash.
    $arguments = '--ucp-config-file="' + $settingsPath + '"'
    Start-Process -FilePath $executable -WorkingDirectory $gameRoot -ArgumentList $arguments
} catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path (Get-Location).Path 'ucp/replays/restart-error.txt')
    exit 1
}
]=]
