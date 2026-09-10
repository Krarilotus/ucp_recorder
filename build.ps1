param (
    [ValidateSet('Release', 'Debug')][string]$BuildType = 'Release',
    [string]$UCP3Path = ''
)

$ErrorActionPreference = 'Stop'
# UCP's custom-build entry point; the shared packager owns file/profile selection.
python "$PSScriptRoot/tools/store_package.py" --configuration $BuildType
if ($LASTEXITCODE -ne 0) { throw 'Recorder store package preparation failed' }
