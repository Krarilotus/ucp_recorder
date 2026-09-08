<# Exercise the shipped x86 Lua and MemoryZip libraries without starting a game.
   Run with SysWOW64 Windows PowerShell. Only fixed test files are extracted to
   a new temporary directory; game installation files are read-only inputs. #>
param([Parameter(Mandatory=$true)][string]$GameDirectory)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Run this check with 32-bit Windows PowerShell (SysWOW64).' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ReplayZipLua {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern IntPtr LoadLibraryW(string path);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern IntPtr luaL_newstate();
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern void luaL_openlibs(IntPtr state);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern IntPtr lua_pushstring(IntPtr state, string text);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern void lua_setglobal(IntPtr state, string name);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int luaL_loadfilex(IntPtr state, string path, IntPtr mode);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern int lua_pcallk(IntPtr state, int args, int results, int error,
        IntPtr context, IntPtr continuation);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern IntPtr lua_tolstring(IntPtr state, int index, IntPtr length);
    [DllImport("lua.dll", CallingConvention=CallingConvention.Cdecl)]
    public static extern void lua_close(IntPtr state);
}
'@
$gamePath = (Resolve-Path -LiteralPath $GameDirectory).Path
$sourcePath = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$testPath = Join-Path ([IO.Path]::GetTempPath()) ('recorder-zip-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testPath) | Out-Null
$state = [IntPtr]::Zero
$archive = $null
try {
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $gamePath 'ucp/modules/map-extensions-1.0.0.zip'))
    foreach ($pair in @(@('luamemzip.dll','luamemzip.dll'), @('mapextensions/handles.lua','handles.lua'))) {
        $entry = $archive.GetEntry($pair[0])
        if (-not $entry) { throw ('Missing shipped entry: ' + $pair[0]) }
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $testPath $pair[1]))
    }
    $archive.Dispose(); $archive = $null
    if ([ReplayZipLua]::LoadLibraryW((Join-Path $gamePath 'lua.dll')) -eq [IntPtr]::Zero) {
        throw ('Cannot load shipped Lua DLL: ' + [Runtime.InteropServices.Marshal]::GetLastWin32Error())
    }
    $state = [ReplayZipLua]::luaL_newstate()
    if ($state -eq [IntPtr]::Zero) { throw 'Cannot allocate Lua state' }
    [ReplayZipLua]::luaL_openlibs($state)
    foreach ($pair in @(@('sourceRoot',$sourcePath), @('testRoot',$testPath))) {
        [ReplayZipLua]::lua_pushstring($state, $pair[1].Replace('\','/')) | Out-Null
        [ReplayZipLua]::lua_setglobal($state, $pair[0])
    }
    $result = [ReplayZipLua]::luaL_loadfilex($state, (Join-Path $PSScriptRoot 'check_automarket_zip_windows.lua'), [IntPtr]::Zero)
    if ($result -eq 0) {
        $result = [ReplayZipLua]::lua_pcallk($state, 0, 0, 0, [IntPtr]::Zero, [IntPtr]::Zero)
    }
    if ($result -ne 0) {
        throw [Runtime.InteropServices.Marshal]::PtrToStringAnsi([ReplayZipLua]::lua_tolstring($state, -1, [IntPtr]::Zero))
    }
    # A second ZIP reader checks the emitted archive independently of MemoryZip.
    $archive = [IO.Compression.ZipFile]::OpenRead((Join-Path $testPath 'automarket.zip'))
    if ($archive.Entries.Count -ne 1) { throw 'Unexpected custom ZIP entries' }
    $entry = $archive.GetEntry('automarket/automarketplayerdata.bin')
    if (-not $entry -or $entry.Length -ne 2416) { throw 'Incorrect Automarket saved entry' }
    $input = $entry.Open()
    try {
        $bytes = New-Object IO.MemoryStream
        $input.CopyTo($bytes)
        $actual = $bytes.ToArray()
        $bytes.Dispose()
        if ($actual[0] -ne 2 -or $actual[1] -ne 0 -or $actual[2] -ne 0 -or $actual[3] -ne 0) {
            throw 'Incorrect Automarket layout header'
        }
        for ($index = 4; $index -lt 2416; $index++) {
            if ($actual[$index] -ne (($index - 4) % 256)) { throw 'Automarket bytes differ' }
        }
    } finally { $input.Dispose() }
    Write-Output 'PASS: actual recorder adapter, shipped x86 Lua/MemoryZip and map-extensions read handle; independent ZIP byte verification'
} finally {
    if ($archive) { $archive.Dispose() }
    if ($state -ne [IntPtr]::Zero) { [ReplayZipLua]::lua_close($state) }
    # Closing Lua releases package.loadlib's handles. Delete only these fixed
    # fixture files and their now-empty directory, never recurse into a path.
    try {
        foreach ($name in @('automarket.zip','handles.lua','luamemzip.dll')) {
            $file = Join-Path $testPath $name
            if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
        }
        [IO.Directory]::Delete($testPath)
    } catch { Write-Warning ('Test cleanup incomplete: ' + $testPath + ': ' + $_.Exception.Message) }
}
