"""UCP store and downloadable ZIPs must ship the same runtime contents."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from module_package import build_module
from store_package import stage_store


class StorePackageTests(unittest.TestCase):
    def test_store_matches_shared_package_and_replaces_previous_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            for name in ('definition.yml', 'options.yml', 'init.lua', 'README.md', 'CHANGELOG.md'):
                shutil.copy2(ROOT / name, source / name)
            for name in ('code', 'locale', 'docs', 'tools'):
                shutil.copytree(ROOT / name, source / name)
            for configuration, profile in (('Debug', 'diagnostic'), ('Release', 'release')):
                with self.subTest(configuration=configuration):
                    stage = stage_store(source, configuration)
                    package = build_module(source, root / profile, profile=profile)
                    with zipfile.ZipFile(package.path) as archive:
                        actual = {p.relative_to(stage).as_posix(): p.read_bytes()
                                  for p in stage.rglob('*') if p.is_file()}
                        self.assertEqual(actual, {name: archive.read(name) for name in archive.namelist()})
            self.assertFalse((stage / 'code/rng-attribution.lua').exists())
            self.assertFalse((stage / 'tools').exists())
            self.assertIn('diagnostics=false', (stage / 'code/build-profile.lua').read_text())
