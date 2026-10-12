import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app_config import load_settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def test_defaults_without_env_file(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(self.root)
        self.assertEqual(settings['APP_PORT'], 5000)
        self.assertFalse(settings['DEBUG'])
        self.assertEqual(settings['DATABASE'], str(self.root / 'instance' / 'contracts.sqlite3'))

    def test_file_values_and_environment_priority_without_global_changes(self):
        (self.root / '.env').write_text('APP_PORT=5050\nAPP_DEBUG=false\nDOCUMENTS_PAGE_SIZE=12\n'
                                     'SEARCH_MIN_SCORE=0.45\nDATABASE=data/my.sqlite3\nSECRET_KEY=test-secret\n', encoding='utf-8')
        with patch.dict(os.environ, {'APP_PORT': '6060'}, clear=True):
            settings = load_settings(self.root)
            self.assertNotIn('SECRET_KEY', os.environ)
        self.assertEqual(settings['APP_PORT'], 6060)
        self.assertFalse(settings['DEBUG'])
        self.assertEqual(settings['DOCUMENTS_PAGE_SIZE'], 12)
        self.assertEqual(settings['SEARCH_MIN_SCORE'], 0.45)
        self.assertEqual(settings['DATABASE'], str(self.root / 'data' / 'my.sqlite3'))
        self.assertEqual(settings['SECRET_KEY'], 'test-secret')

    def test_invalid_values_fail_clearly(self):
        for name, value in [('APP_PORT', '0'), ('APP_PORT', 'hello'), ('DOCUMENTS_PAGE_SIZE', '0'),
                            ('MAX_UPLOAD_MB', '-1'), ('APP_DEBUG', 'maybe'), ('SEARCH_MIN_SCORE', 'nan'),
                            ('SEARCH_MIN_SCORE', '2')]:
            with self.subTest(name=name, value=value), patch.dict(os.environ, {name: value}, clear=True):
                with self.assertRaisesRegex(ValueError, name):
                    load_settings(self.root)
