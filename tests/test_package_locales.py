"""A fresh install must expose translated options and the correct option owners."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {'en', 'de', 'fr', 'es', 'hu', 'tr', 'ru', 'ch', 'fa'}


class PackageLocaleTests(unittest.TestCase):
    def test_all_launcher_languages_cover_every_option_without_unused_entries(self):
        options = (ROOT / 'options.yml').read_text(encoding='utf-8')
        keys = set(re.findall(r'{{([^{}]+)}}', options))
        self.assertEqual(len(keys), 14)
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
