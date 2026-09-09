"""The trusted publisher must ship the documented tools without executing PR code."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import pr_releases as publisher


class ReleasePackageTests(unittest.TestCase):
    def test_profile_source_produces_both_artifacts_with_checksums(self):
        import hashlib
        import shutil
        source_root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source'
            for name in ('definition.yml','options.yml','init.lua','README.md','CHANGELOG.md'):
                source.mkdir(exist_ok=True); shutil.copy2(source_root/name,source/name)
            for name in ('code','docs','locale','tools'):
                shutil.copytree(source_root/name,source/name)
            previous=Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ,PR_BUILD=json.dumps(dict(pr=46,sha='a'*40))):publisher.package()
            finally:os.chdir(previous)
            metadata=json.loads((root/'out/build.json').read_text())
            version=metadata['version']
            for filename,key in ((f'recorder-{version}.zip','sha256'),
                                 (f'recorder-{version}-diagnostics-bundle.zip','diagnosticsSha256')):
                self.assertEqual(hashlib.sha256((root/'out'/filename).read_bytes()).hexdigest(),metadata[key])
                self.assertTrue((root/'out'/(filename+'.sha256')).is_file())
    def test_both_documented_tools_ship_without_running_source_builder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'source'
            (source/'tools').mkdir(parents=True)
            (source/'code').mkdir()
            (source/'docs').mkdir()
            (source/'definition.yml').write_text('name: recorder\nversion: 0.30.0\n')
            for name in ('options.yml','init.lua','README.md','CHANGELOG.md'):
                (source/name).write_text('test')
            for name in ('compare_multiplayer.py','inspect_replay.py','build.py'):
                (source/'tools'/name).write_text("raise RuntimeError('PR code must not execute during packaging')\n")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, PR_BUILD=json.dumps(dict(pr=33, sha='a'*40))):
                    publisher.package()
            finally:
                os.chdir(previous)
            with zipfile.ZipFile(root/'out/recorder-0.30.0.zip') as archive:
                self.assertIsNone(archive.testzip())
                for name in ('compare_multiplayer.py','inspect_replay.py'):
                    self.assertEqual(archive.read('tools/'+name), (source/'tools'/name).read_bytes())
                self.assertNotIn('tools/build.py', archive.namelist())
