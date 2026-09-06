"""Run the actual PowerShell helper with process waiting/launching replaced by fakes.

No game or other application is started. The helper still performs real path,
JSON and file-hash checks inside a temporary directory.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from lupa.luajit21 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell helper')
class RestartHelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='replay helper ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root/'ucp/replays'
        self.session = self.folder/'test-recording'
        self.session.mkdir(parents=True)
        self.exe = self.root/'Crusader test.exe'
        self.exe.write_bytes(b'test executable; never launched')
        self.settings = self.session/'ucp-config.yml'
        self.settings.write_bytes(b'active: true\n')
        self.manifest = {'id': 'test-recording', 'status': 'complete',
                         'executable': hashlib.sha256(self.exe.read_bytes()).hexdigest(),
                         'settingsHash': hashlib.sha256(self.settings.read_bytes()).hexdigest()}
        (self.session/'manifest.json').write_text(json.dumps(self.manifest))
        (self.folder/'restart-request.json').write_text(json.dumps({
            'id': 'test-recording', 'executable': str(self.exe), 'processId': 123}))
        script = LuaRuntime().execute((ROOT/'code/restart-script.lua').read_text())
        (self.root/'helper.ps1').write_text(script, encoding='utf-8-sig')
        (self.root/'runner.ps1').write_text('''
$ErrorActionPreference = 'Stop'
function Get-FileHash { throw 'Optional PowerShell script module is unavailable' }
function Get-Process {
    param($Id,$ErrorAction)
    $process = [pscustomobject]@{ Path = (Join-Path (Get-Location).Path 'Crusader test.exe') }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
        Set-Content -LiteralPath 'waited.txt' -Value 'waited'
        if (Test-Path -LiteralPath 'swap-executable.txt') {
            Set-Content -LiteralPath 'Crusader test.exe' -Value 'updated executable'
        }
    }
    return $process
}
function Start-Process {
    param($FilePath,$WorkingDirectory,$ArgumentList)
    if (-not (Test-Path -LiteralPath 'waited.txt')) { throw 'Launch occurred before waiting' }
    @{executable=$FilePath; cwd=$WorkingDirectory; arguments=$ArgumentList; replay=$env:UCP_RECORDER_REPLAY} |
        ConvertTo-Json | Set-Content -LiteralPath 'launch.json' -Encoding UTF8
}
& './helper.ps1'
exit $LASTEXITCODE
''', encoding='utf-8-sig')

    def run_helper(self):
        powershell = Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
        result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive',
                               '-ExecutionPolicy', 'Bypass', '-File', str(self.root/'runner.ps1')],
                              cwd=self.root, capture_output=True, text=True, timeout=20,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        error = self.folder/'restart-error.txt'
        if error.exists():
            result.stderr += error.read_text(encoding='utf-8', errors='replace')
        return result

    def test_waits_then_requests_recorded_settings_without_overwriting_default(self):
        normal = self.root/'ucp-config.yml'
        normal.write_text('normal settings')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        launch = json.loads((self.root/'launch.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(launch['executable'], str(self.exe))
        self.assertEqual(launch['arguments'], f'--ucp-config-file="{self.settings}"')
        self.assertEqual(launch['replay'], 'test-recording')
        self.assertEqual(normal.read_text(), 'normal settings')

    def test_settings_modified_while_waiting_do_not_launch(self):
        self.settings.write_text('modified after recording')
        result = self.run_helper()
        self.assertFalse((self.root/'launch.json').exists())
        self.assertTrue((self.folder/'restart-error.txt').exists(), result.stderr)

    def test_wrong_executable_is_rejected_before_waiting(self):
        self.exe.write_text('a different executable')
        result = self.run_helper()
        self.assertFalse((self.root/'launch.json').exists())
        self.assertFalse((self.root/'waited.txt').exists())
        self.assertTrue((self.folder/'restart-error.txt').exists(), result.stderr)

    def test_executable_changed_while_waiting_is_checked_again(self):
        (self.root/'swap-executable.txt').touch()
        result = self.run_helper()
        self.assertTrue((self.root/'waited.txt').exists(), result.stderr)
        self.assertFalse((self.root/'launch.json').exists())
        self.assertTrue((self.folder/'restart-error.txt').exists(), result.stderr)

    def pinned_profile(self):
        pinned=self.session/'replay-config.yml'
        pinned.write_text('{"active":true,"config-full":{"load-order":[{"extension":"recorder","version":"0.25.0"}]}}')
        environment=self.session/'environment.json'
        environment.write_text('{"framework":"test framework"}')
        self.manifest.update(settingsCapture='resolved-v1',restartSettingsHash=hashlib.sha256(pinned.read_bytes()).hexdigest(),
                             environmentHash=hashlib.sha256(environment.read_bytes()).hexdigest())
        (self.session/'manifest.json').write_text(json.dumps(self.manifest))
        return pinned,environment

    def test_resolved_capture_launches_its_pinned_profile(self):
        pinned,_=self.pinned_profile()
        original=self.settings.read_bytes()
        result=self.run_helper()
        self.assertEqual(result.returncode,0,result.stderr)
        launch=json.loads((self.root/'launch.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(launch['arguments'],f'--ucp-config-file="{pinned}"')
        self.assertEqual(self.settings.read_bytes(),original)

    def test_changed_pinned_profile_or_environment_never_launches(self):
        pinned,environment=self.pinned_profile()
        good=pinned.read_bytes()
        pinned.write_text('changed pinned options')
        self.run_helper()
        self.assertFalse((self.root/'launch.json').exists())
        pinned.write_bytes(good); environment.write_text('changed environment')
        self.run_helper()
        self.assertFalse((self.root/'launch.json').exists())

    def test_unknown_settings_profile_never_waits_or_launches(self):
        self.pinned_profile()
        self.manifest['settingsCapture']='unknown'
        (self.session/'manifest.json').write_text(json.dumps(self.manifest))
        self.run_helper()
        self.assertFalse((self.root/'waited.txt').exists())
        self.assertFalse((self.root/'launch.json').exists())
