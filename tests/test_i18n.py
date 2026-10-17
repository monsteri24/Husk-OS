"""System 2 supports English only; preserved catalogs cannot opt it into Finnish."""
import gettext
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class EnglishTranslationTests(unittest.TestCase):
    def setUp(self):
        self.i18n = importlib.import_module('ownos.i18n')
        self.addCleanup(self.i18n.configure)

    def test_default_ignores_finnish_host_language(self):
        with patch.dict(os.environ, {'LANGUAGE': 'fi:en', 'LANG': 'fi_FI.UTF-8',
                                     'LC_ALL': 'fi_FI.UTF-8'}):
            with patch.object(gettext, 'translation', wraps=gettext.translation) as load:
                self.i18n.configure()
        self.assertEqual(self.i18n.SUPPORTED_LANGUAGES, ('en',))
        self.assertEqual(load.call_args.kwargs['languages'], ['en'])
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_finnish_locale_alias_falls_back_to_english(self):
        with patch.object(gettext, 'translation', wraps=gettext.translation) as load:
            self.i18n.configure(language='fi_FI.UTF-8')
        self.assertEqual(load.call_args.kwargs['languages'], ['en'])

    def test_unsupported_language_never_uses_the_host_language(self):
        with patch.dict(os.environ, {'LANGUAGE': 'fi', 'LANG': 'fi_FI.UTF-8'}):
            with patch.object(gettext, 'translation', wraps=gettext.translation) as load:
                self.i18n.configure(language='not-supported')
        self.assertEqual(load.call_args.kwargs['languages'], ['en'])
        self.assertEqual(self.i18n.gettext_('Network'), 'Network')

    def test_missing_future_catalog_directory_keeps_english_source(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog_directory = Path(directory) / 'future-catalogs'
            self.i18n.configure(language='en_GB.UTF-8', localedir=catalog_directory)
            self.assertEqual(self.i18n.gettext('Open {application}').format(application='Steam'),
                             'Open Steam')
            self.assertEqual(self.i18n.ngettext('{count} item', '{count} items', 1).format(count=1),
                             '1 item')
            self.assertEqual(self.i18n.ngettext('{count} item', '{count} items', 0).format(count=0),
                             '0 items')
            self.assertEqual(self.i18n.ngettext('{count} item', '{count} items', 12).format(count=12),
                             '12 items')

    def test_entry_points_follow_later_catalog_configuration(self):
        translate = self.i18n._

        class EnglishCatalog(gettext.NullTranslations):
            def gettext(self, message):
                return {'Settings': 'Husk Settings'}.get(message, message)

        with patch.object(gettext, 'translation', return_value=EnglishCatalog()) as load:
            self.i18n.configure(localedir='/tmp/husk-test-catalogs')
        self.assertEqual(load.call_args.args[0], 'huskos')
        self.assertTrue(load.call_args.kwargs['fallback'])
        self.assertEqual(translate('Settings'), 'Husk Settings')

    def test_corrupt_catalog_does_not_stop_an_application(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = Path(directory) / 'en/LC_MESSAGES/huskos.mo'
            catalog.parent.mkdir(parents=True)
            for contents in (b'', b'invalid catalog', b'\xde\x12\x04\x95' + b'\x00' * 8):
                with self.subTest(contents=contents):
                    catalog.write_bytes(contents)
                    try:
                        self.i18n.configure(language='en', localedir=directory)
                    except Exception as exc:
                        self.fail('A corrupt catalog prevented English fallback: ' + str(exc))
                    self.assertEqual(self.i18n._('Settings'), 'Settings')


class LanguageConfigurationTests(unittest.TestCase):
    def setUp(self):
        from ownos.config import ConfigStore
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = ConfigStore(Path(self.tmp.name) / 'settings.json')

    def test_new_and_existing_settings_default_to_english(self):
        self.assertEqual(self.store.load().get('language'), 'en')
        self.store.path.write_text(json.dumps({'overlay': True}))
        settings = self.store.load()
        self.assertEqual(settings.get('language'), 'en')
        self.assertTrue(settings['overlay'])

    def test_english_choice_survives_an_independent_store(self):
        settings = self.store.load(); settings['language'] = 'en'
        self.store.save(settings)
        self.assertEqual(type(self.store)(self.store.path).load().get('language'), 'en')

    def test_invalid_language_save_is_rejected(self):
        for language in ('fi', 'fi_FI', 'fi-FI', 'de', 'fi:en', '../../fi', None, ['fi'], {'fi': True}, 1):
            with self.subTest(language=language), self.assertRaises(ValueError):
                settings = self.store.load(); settings['language'] = language
                self.store.save(settings)

    def test_invalid_saved_language_retains_other_valid_settings(self):
        for language in ('fi', 'fi_FI', 'fi-FI', 'xx', 'fi_FI.UTF-8', None, ['fi'], {'fi': True}, 1):
            with self.subTest(language=language):
                self.store.path.write_text(json.dumps({'language': language, 'overlay': True}))
                settings = self.store.load()
                self.assertEqual(settings.get('language'), 'en')
                self.assertTrue(settings['overlay'])

    def test_corrupt_json_retains_english_default(self):
        self.store.path.write_bytes(b'\xff{"language":"fi"')
        self.assertEqual(self.store.load().get('language'), 'en')


class EnglishOnlyReleaseTests(unittest.TestCase):
    def setUp(self):
        from ownos.config import ConfigStore
        self.i18n = importlib.import_module('ownos.i18n')
        self.addCleanup(self.i18n.configure)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ConfigStore(self.root / 'settings.json')

    def preserved_catalog_directory(self):
        source = ROOT / 'locale/fi/LC_MESSAGES/huskos.po'
        self.assertTrue(source.is_file(), 'Preserve the postponed Finnish source catalog')
        directory = self.root / 'locale'
        target = directory / 'fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['msgfmt', '--check', '--check-format', str(source), '-o', str(target)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return directory

    def test_finnish_catalog_cannot_enable_finnish_in_system2(self):
        directory = self.preserved_catalog_directory(); translate = self.i18n._
        with patch.dict(os.environ, {'LANGUAGE': 'fi:en', 'LANG': 'fi_FI.UTF-8'}):
            for language in ('fi', 'fi_FI', 'fi-FI', 'fi_FI.UTF-8'):
                with self.subTest(language=language):
                    self.assertEqual(self.i18n.configure(language, localedir=directory), 'en')
                    self.assertEqual(translate('Settings'), 'Settings')
                    for count, expected in [(0, '0 items'), (1, '1 item'), (2, '2 items')]:
                        self.assertEqual(self.i18n.ngettext('{count} item', '{count} items', count).format(count=count), expected)

    def test_saved_finnish_choice_loads_as_english_in_a_fresh_process(self):
        directory = self.preserved_catalog_directory()
        program = '''import json, sys
from ownos.config import ConfigStore
from ownos.i18n import configure_saved, _, ngettext
store = ConfigStore(sys.argv[1])
language = configure_saved(store, localedir=sys.argv[2])
print(json.dumps([language, _('Settings'), ngettext('{count} item', '{count} items', 0).format(count=0), store.load()['overlay']]))
'''
        for language in ('fi', 'fi_FI', 'fi_FI.UTF-8'):
            with self.subTest(language=language):
                self.store.path.write_text(json.dumps({'language': language, 'overlay': True}))
                result = subprocess.run([sys.executable, '-c', program, str(self.store.path), str(directory)],
                                        env=dict(os.environ, PYTHONPATH=str(ROOT / 'src'), LANGUAGE='fi:en', LANG='C'),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), ['en', 'Settings', '0 items', True])

    def test_default_store_ignores_saved_finnish_choice(self):
        directory = self.preserved_catalog_directory()
        store = type(self.store)(self.root / 'config/ownos/settings.json')
        store.path.parent.mkdir(parents=True)
        store.path.write_text(json.dumps({'language': 'fi', 'overlay': True}))
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config'), 'LANGUAGE': 'fi'}):
            self.assertEqual(self.i18n.configure_saved(localedir=directory), 'en')
        self.assertEqual(self.i18n._('Settings'), 'Settings')
        self.assertTrue(store.load()['overlay'])

    def test_unused_finnish_catalog_cannot_break_startup(self):
        target = self.root / 'locale/fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True); target.write_bytes(b'broken catalog')
        self.assertEqual(self.i18n.configure('fi', localedir=self.root / 'locale'), 'en')
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_saved_invalid_or_corrupt_choice_remains_english(self):
        for contents in ('{"language":"xx","overlay":true}', '{"language":["fi"]}', '{broken'):
            with self.subTest(contents=contents):
                self.store.path.write_text(contents)
                with patch.dict(os.environ, {'LANGUAGE': 'fi', 'LANG': 'fi_FI.UTF-8'}):
                    self.assertEqual(self.i18n.configure_saved(self.store, localedir=self.root / 'missing'), 'en')
                self.assertEqual(self.i18n._('Settings'), 'Settings')


if __name__ == '__main__':
    unittest.main()
