import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile
from tools.module_package import build_module, build_diagnostic_bundle, DIAGNOSTIC_MODULES


class BuildProfileTests(unittest.TestCase):
    def test_release_and_inner_diagnostic_module_have_matching_identity(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary); source=root/'source'; (source/'code').mkdir(parents=True)
            (source/'definition.yml').write_text('name: recorder\nversion: 1.2.3\n')
            for name in ('init.lua','README.md','CHANGELOG.md'):(source/name).write_text('source must not execute')
            (source/'options.yml').write_text('meta:\n  version: 1.0.0\noptions:\n- url: recorder.singleplayerRngDiagnostics\n  value: false\n- url: recorder.autoRecord\n  value: true\n')
            (source/'code/build-profile.lua').write_text('return {diagnostics=true}')
            (source/'code/tick-journal.lua').write_text('essential')
            for name in DIAGNOSTIC_MODULES:(source/'code'/name).write_text('optional')
            release=build_module(source,root/'out',profile='release')
            bundle=build_diagnostic_bundle(source,root/'out')
            with zipfile.ZipFile(release.path) as r,zipfile.ZipFile(bundle.path) as outer:
                with zipfile.ZipFile(io.BytesIO(outer.read(release.path.name))) as d:
                    self.assertEqual(r.read('definition.yml'),d.read('definition.yml'))
                    self.assertEqual(r.read('code/tick-journal.lua'),d.read('code/tick-journal.lua'))
                    self.assertIn(b'diagnostics=false',r.read('code/build-profile.lua'))
                    self.assertIn(b'diagnostics=true',d.read('code/build-profile.lua'))
                    self.assertNotIn(b'RngDiagnostics',r.read('options.yml'))
                    self.assertIn(b'autoRecord',r.read('options.yml'))
                    for name in DIAGNOSTIC_MODULES:
                        self.assertNotIn('code/'+name,r.namelist());self.assertIn('code/'+name,d.namelist())
