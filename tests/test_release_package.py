"""The trusted publisher must ship the documented tools without executing PR code."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('pr_releases', Path(__file__).resolve().parents[1]/'tools/pr_releases.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class ReleasePackageTests(unittest.TestCase):
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
