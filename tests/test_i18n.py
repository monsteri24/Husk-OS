"""Explicit Husk language choices and safe English fallbacks."""
import ast
import gettext
import importlib
import json
import os
import string
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
        self.assertEqual(self.i18n.SUPPORTED_LANGUAGES, ('en', 'fi'))
        self.assertEqual(load.call_args.kwargs['languages'], ['en'])
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_finnish_locale_alias_selects_the_reviewed_catalog(self):
        with patch.object(gettext, 'translation', wraps=gettext.translation) as load:
            self.i18n.configure(language='fi_FI.UTF-8')
        self.assertEqual(load.call_args.kwargs['languages'], ['fi'])

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

    def test_finnish_choice_survives_an_independent_store(self):
        settings = self.store.load(); settings['language'] = 'fi'
        self.store.save(settings)
        self.assertEqual(type(self.store)(self.store.path).load().get('language'), 'fi')

    def test_invalid_language_save_is_rejected(self):
        for language in ('de', 'fi:en', '../../fi', None, ['fi'], {'fi': True}, 1):
            with self.subTest(language=language), self.assertRaises(ValueError):
                settings = self.store.load(); settings['language'] = language
                self.store.save(settings)

    def test_invalid_saved_language_retains_other_valid_settings(self):
        for language in ('xx', 'fi_FI.UTF-8', None, ['fi'], {'fi': True}, 1):
            with self.subTest(language=language):
                self.store.path.write_text(json.dumps({'language': language, 'overlay': True}))
                settings = self.store.load()
                self.assertEqual(settings.get('language'), 'en')
                self.assertTrue(settings['overlay'])

    def test_corrupt_json_retains_english_default(self):
        self.store.path.write_bytes(b'\xff{"language":"fi"')
        self.assertEqual(self.store.load().get('language'), 'en')


class FinnishCatalogTests(unittest.TestCase):
    def setUp(self):
        from ownos.config import ConfigStore
        self.i18n = importlib.import_module('ownos.i18n')
        self.addCleanup(self.i18n.configure)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = ConfigStore(self.root / 'settings.json')

    def compile_catalog(self):
        source = ROOT / 'locale/fi/LC_MESSAGES/huskos.po'
        self.assertTrue(source.is_file(), 'The reviewed Finnish catalog must be shipped')
        directory = self.root / 'locale'
        target = directory / 'fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['msgfmt', '--check', '--check-format', str(source), '-o', str(target)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return directory

    def test_finnish_messages_and_plural_forms(self):
        self.i18n.configure('fi', localedir=self.compile_catalog())
        for source, expected in [('Settings', 'Asetukset'), ('Husk Files', 'Husk-tiedostot'),
                                 ('Cancel', 'Peruuta'), ('Close', 'Sulje'), ('Minimize', 'Pienennä')]:
            with self.subTest(source=source):
                self.assertEqual(self.i18n._(source), expected)
        for count, expected in [(0, '0 kohdetta'), (1, '1 kohde'), (2, '2 kohdetta'), (12, '12 kohdetta')]:
            with self.subTest(count=count):
                self.assertEqual(self.i18n.ngettext('{count} item', '{count} items', count).format(count=count), expected)

    def test_finnish_locale_aliases_update_an_imported_entry_point(self):
        directory = self.compile_catalog(); translate = self.i18n._
        for language in ('fi', 'fi-FI', 'fi_FI.UTF-8'):
            with self.subTest(language=language):
                self.assertEqual(self.i18n.configure(language, localedir=directory), 'fi')
                self.assertEqual(translate('Settings'), 'Asetukset')

    def test_unsupported_or_malformed_choices_clear_a_previous_translation(self):
        directory = self.compile_catalog()
        for language in ('de', 'fi:en', '../../fi', '', None, ['fi'], {'fi': True}, 1):
            with self.subTest(language=language):
                self.i18n.configure('fi', localedir=directory)
                self.assertEqual(self.i18n.configure(language, localedir=directory), 'en')
                self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_missing_catalog_clears_a_previous_translation(self):
        self.i18n.configure('fi', localedir=self.compile_catalog())
        self.assertEqual(self.i18n.configure('fi', localedir=self.root / 'missing'), 'en')
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_corrupt_finnish_catalog_clears_a_previous_translation(self):
        self.i18n.configure('fi', localedir=self.compile_catalog())
        directory = self.root / 'broken'
        target = directory / 'fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True); target.write_bytes(b'broken catalog')
        self.assertEqual(self.i18n.configure('fi', localedir=directory), 'en')
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_catalog_with_unknown_encoding_falls_back_to_english(self):
        directory = self.compile_catalog()
        contents = (directory / 'fi/LC_MESSAGES/huskos.mo').read_bytes()
        self.assertIn(b'charset=UTF-8', contents)
        broken = self.root / 'unknown-encoding'
        target = broken / 'fi/LC_MESSAGES/huskos.mo'
        target.parent.mkdir(parents=True)
        target.write_bytes(contents.replace(b'charset=UTF-8', b'charset=BAD-8'))
        try:
            language = self.i18n.configure('fi', localedir=broken)
        except Exception as exc:
            self.fail('An invalid catalog encoding prevented English fallback: ' + str(exc))
        self.assertEqual(language, 'en')
        self.assertEqual(self.i18n._('Settings'), 'Settings')

    def test_catalog_covers_husk_ui_messages(self):
        directory = self.compile_catalog()
        catalog = gettext.translation('huskos', localedir=directory, languages=['fi'])
        missing = []
        for source in (ROOT / 'src/ownos/ui').glob('*.py'):
            for node in ast.walk(ast.parse(source.read_text(encoding='utf-8'))):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name): continue
                if node.func.id not in ('_', 'gettext', 'gettext_', 'ngettext') or not node.args: continue
                if not isinstance(node.args[0], ast.Constant): continue
                message = node.args[0].value
                key = (message, 0) if node.func.id == 'ngettext' else message
                if key not in catalog._catalog: missing.append((source.name, message))
        self.assertEqual(missing, [], 'Every Husk-owned UI message needs a Finnish catalog entry')

    def test_catalog_preserves_named_format_fields(self):
        directory = self.compile_catalog()
        catalog = gettext.translation('huskos', localedir=directory, languages=['fi'])
        formatter = string.Formatter()
        fields = lambda text: sorted((name, spec, conversion) for _, name, spec, conversion in formatter.parse(text) if name is not None)
        for key, translation in catalog._catalog.items():
            source = key[0] if isinstance(key, tuple) else key
            if not source: continue
            with self.subTest(source=source):
                self.assertEqual(fields(source), fields(translation))

    def test_saved_choice_loads_in_a_fresh_process(self):
        directory = self.compile_catalog()
        settings = self.store.load(); settings['language'] = 'fi'; self.store.save(settings)
        program = '''import json, sys
from ownos.config import ConfigStore
from ownos.i18n import configure_saved, _, ngettext
language = configure_saved(ConfigStore(sys.argv[1]), localedir=sys.argv[2])
print(json.dumps([language, _('Settings'), ngettext('{count} item', '{count} items', 0).format(count=0)]))
'''
        result = subprocess.run([sys.executable, '-c', program, str(self.store.path), str(directory)],
                                env=dict(os.environ, PYTHONPATH=str(ROOT / 'src'), LANGUAGE='de:en', LANG='C'),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ['fi', 'Asetukset', '0 kohdetta'])

    def test_default_store_reads_saved_per_user_choice(self):
        directory = self.compile_catalog()
        store = type(self.store)(self.root / 'config/ownos/settings.json')
        settings = store.load(); settings['language'] = 'fi'; store.save(settings)
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config')}):
            self.assertEqual(self.i18n.configure_saved(localedir=directory), 'fi')
        self.assertEqual(self.i18n._('Settings'), 'Asetukset')

    def test_saved_invalid_or_corrupt_choice_resets_to_english(self):
        directory = self.compile_catalog()
        for contents in ('{"language":"xx","overlay":true}', '{"language":["fi"]}', '{broken'):
            with self.subTest(contents=contents):
                self.i18n.configure('fi', localedir=directory)
                self.store.path.write_text(contents)
                with patch.dict(os.environ, {'LANGUAGE': 'fi', 'LANG': 'fi_FI.UTF-8'}):
                    self.assertEqual(self.i18n.configure_saved(self.store, localedir=directory), 'en')
                self.assertEqual(self.i18n._('Settings'), 'Settings')


if __name__ == '__main__':
    unittest.main()
