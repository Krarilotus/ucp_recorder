import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from tools.module_package import build_module, build_diagnostic_bundle, DIAGNOSTIC_MODULES

class ModulePackageTests(unittest.TestCase):
    def test_actual_release_and_diagnostic_payloads_keep_distinct_capabilities(self):
        import io
        source=Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            release=build_module(source,root,profile='release')
            bundle=build_diagnostic_bundle(source,root)
            with zipfile.ZipFile(release.path) as production, zipfile.ZipFile(bundle.path) as outer:
                with zipfile.ZipFile(io.BytesIO(outer.read(release.path.name))) as diagnostic:
                    self.assertIn(b'diagnostics=false',production.read('code/build-profile.lua'))
                    self.assertIn(b'diagnostics=true',diagnostic.read('code/build-profile.lua'))
                    for name in DIAGNOSTIC_MODULES:
                        self.assertNotIn('code/'+name,production.namelist())
                        self.assertIn('code/'+name,diagnostic.namelist())
                    for name in ('multiplayer-capture','network-observer','world-hash-observer',
                                 'tick-journal','replay-preparation','playback-controls','history-native'):
                        member='code/'+name+'.lua'
                        self.assertEqual(production.read(member),diagnostic.read(member))
                    self.assertFalse(any(name.startswith('tools/') for name in production.namelist()))
                    self.assertIn('tools/inspect_replay.py',diagnostic.namelist())
                    self.assertEqual(production.read('definition.yml'),diagnostic.read('definition.yml'))
                    for image in ('replay-history.jpg','replay-controls.jpg'):
                        member='docs/images/'+image
                        self.assertEqual(production.read(member),diagnostic.read(member))
                        self.assertTrue(production.read(member).startswith(b'\xff\xd8\xff'))
                    self.assertNotIn(b'RngDiagnostics',production.read('options.yml'))
                    self.assertNotIn(b'multiplayerDiagnostics',production.read('options.yml'))
                    self.assertIn(b'recorder.autoRecord',production.read('options.yml'))
                    self.assertIn(b'recorder.singleplayerRngDiagnostics',diagnostic.read('options.yml'))
    def test_release_contains_translations_and_tools_without_running_source(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'definition.yml').write_text('name: recorder\nversion: 1.2.3\n')
            for name in ('options.yml', 'init.lua', 'README.md', 'CHANGELOG.md'):
                (source / name).write_text('fixture')
            for directory in ('locale', 'code', 'tools', 'tests'):
                (source / directory).mkdir()
            for name in ('en.yml', 'description-en.md'):
                (source / 'locale' / name).write_text('translated contents')
            for name in ('inspect_replay.py', 'compare_multiplayer.py', 'build.py'):
                (source / 'tools' / name).write_text("raise RuntimeError('source code must not run')")
            (source / 'code' / 'main.lua').write_text('error("source code must not run")')
            (source / 'tests' / 'private.py').write_text('excluded')
            package = build_module(source, root / 'out')
            self.assertEqual(package.path.name, f'recorder-{package.version}.zip')
            self.assertEqual(package.sha256, hashlib.sha256(package.path.read_bytes()).hexdigest())
            with zipfile.ZipFile(package.path) as archive:
                self.assertIsNone(archive.testzip())
                for path in (source / 'locale').iterdir():
                    self.assertEqual(archive.read('locale/' + path.name), path.read_bytes())
                self.assertIn('tools/inspect_replay.py', archive.namelist())
                self.assertIn('tools/compare_multiplayer.py', archive.namelist())
                self.assertNotIn('tools/build.py', archive.namelist())
                self.assertFalse(any(name.startswith(('tests/', '.github/')) for name in archive.namelist()))

    def test_missing_member_and_wrong_identity_fail_before_creating_zip(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'definition.yml').write_text('name: another-module\nversion: 1.0.0\n')
            with self.assertRaisesRegex(ValueError, 'identity'):
                build_module(root, root / 'out')
            (root / 'definition.yml').write_text('name: recorder\nversion: 1.0.0\n')
            with self.assertRaisesRegex(ValueError, 'missing'):
                build_module(root, root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_external_symlink_is_not_packaged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (root / 'outside.yml').write_text('name: recorder\nversion: 1.0.0\n')
            try:
                (source / 'definition.yml').symlink_to(root / 'outside.yml')
            except OSError as error:
                self.skipTest('Symlink creation unavailable: ' + str(error))
            with self.assertRaisesRegex(ValueError, 'outside'):
                build_module(source, root / 'out')
