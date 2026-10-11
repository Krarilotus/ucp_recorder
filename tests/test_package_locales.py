"""A fresh install must expose translated options and the correct option owners."""
import json
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

from tools.module_package import build_module

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {'en', 'de', 'fr', 'es', 'hu', 'tr', 'ru', 'ch', 'fa'}


class PackageLocaleTests(unittest.TestCase):
    def test_all_launcher_languages_cover_every_option_without_unused_entries(self):
        options = (ROOT / 'options.yml').read_text(encoding='utf-8')
        keys = set(re.findall(r'{{([^{}]+)}}', options))
        self.assertEqual(len(keys), 16)
        definition = (ROOT / 'definition.yml').read_text(encoding='utf-8')
        tag_block = re.search(r'^tags:\n((?:[ \t]+-[^\n]+\n?)+)', definition, re.M)
        self.assertIsNotNone(tag_block)
        tags = re.findall(r'^\s+- ([a-z][a-z0-9-]*)$', tag_block[1], re.M)
        self.assertEqual(set(tags), {'replay', 'multiplayer', 'tools'})
        self.assertEqual(len(tags), len(set(tags)))
        keys.update('tags.' + tag for tag in tags)
        locales = list((ROOT / 'locale').glob('*.yml'))
        self.assertEqual({path.stem for path in locales}, LANGUAGES)
        for path in locales:
            with self.subTest(language=path.stem):
                content = json.loads(path.read_text(encoding='utf-8'))  # JSON is valid YAML.
                self.assertEqual(set(content), keys)
                self.assertTrue(all(isinstance(text, str) and text.strip() for text in content.values()))
                self.assertTrue(all('{{' not in text for text in content.values()))

    def test_options_belong_to_recorder_and_do_not_publish_unused_logging_mode(self):
        options = (ROOT / 'options.yml').read_text(encoding='utf-8')
        urls = re.findall(r'^- url: (.+)$', options, re.M)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all(url.startswith('recorder.') for url in urls))
        self.assertIn('recorder.fixedSeed', urls)
        self.assertNotIn('recorder.rngLogMethod', urls)

    def test_packaged_options_have_widgets_labels_and_categories(self):
        # Check the artifact users install, including release-only filtering.
        for profile, count in [('release', 3), ('diagnostic', 7)]:
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                package = build_module(ROOT, Path(folder), profile=profile)
                with zipfile.ZipFile(package.path) as archive:
                    options = archive.read('options.yml').decode('utf-8')
                entries = re.split(r'(?m)^- url: ', options)[1:]
                self.assertEqual(len(entries), count)
                for entry in entries:
                    with self.subTest(option=entry.splitlines()[0]):
                        self.assertIn('category: ["{{recorder_category}}"', entry)
                        if 'type: boolean' in entry:
                            self.assertIn('display: UCP2Switch', entry)
                            self.assertRegex(entry, r'header: "{{\w+_header}}"')
                            self.assertRegex(entry, r'text: "{{\w+_text}}"')
                        else:
                            self.assertIn('type: integer', entry)
                            self.assertIn('display: Number', entry)
                            # Number renders text as its label, not header.
                            self.assertRegex(entry, r'text: "{{\w+_header}}"')
                            self.assertRegex(entry, r'tooltip: "{{\w+_text}}"')
                            self.assertRegex(entry, r'min: -?\d+')
                            self.assertRegex(entry, r'max: \d+')
                if profile == 'release':
                    self.assertNotIn('diagnostics_category', options)
                    self.assertIn('enabled: recorder.useFixedSeed', options)
