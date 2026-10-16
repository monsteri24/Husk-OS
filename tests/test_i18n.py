"""Husk translations remain English until another language is supported."""
import gettext
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


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

    def test_unsupported_language_never_selects_a_finnish_catalog(self):
        with patch.object(gettext, 'translation', wraps=gettext.translation) as load:
            self.i18n.configure(language='fi_FI.UTF-8')
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


if __name__ == '__main__':
    unittest.main()
