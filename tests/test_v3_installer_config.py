import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


class V3InstallerConfiguration(unittest.TestCase):
    def test_installer_is_erase_only_and_requires_separate_confirmation(self):
        settings = yaml.safe_load((ROOT/'installer/calamares/settings.conf').read_text())
        self.assertTrue(settings['prompt-install'])
        steps = next(p['show'] for p in settings['sequence'] if 'show' in p)
        self.assertEqual(steps, ['welcome','keyboard','locale','partition','users','summary'])
        partition = yaml.safe_load((ROOT/'installer/calamares/modules/partition.conf').read_text())
        self.assertFalse(partition['allowManualPartitioning'])
        self.assertEqual(partition['initialPartitioningChoice'], 'none')

    def test_sync_precedes_finished_page_and_no_forced_restart(self):
        settings = yaml.safe_load((ROOT/'installer/calamares/settings.conf').read_text())
        steps = next(p['exec'] for p in settings['sequence'] if 'exec' in p)
        self.assertEqual(steps[-4:], ['bootloader','huskflush','umount','husksync'])
        self.assertEqual(settings['sequence'][-1], {'show':['finishedq']})
        finish = yaml.safe_load((ROOT/'installer/calamares/modules/finishedq.conf').read_text())
        self.assertEqual(finish['restartNowMode'], 'user-unchecked')
        self.assertNotIn(' -i ', finish['restartNowCommand'])

    def test_launcher_is_exact_and_never_directly_executes_a_root_gui(self):
        data = (ROOT/'installer/org.ownos.Install.desktop').read_text()
        self.assertIn('Name=Install Husk OS\n',data)
        self.assertIn('Exec=/usr/bin/husk-install\n',data)
        self.assertIn('Terminal=false',data)

    def test_live_locale_is_english_and_timezone_has_no_geoip_side_effect(self):
        locale = yaml.safe_load((ROOT/'installer/calamares/modules/locale.conf').read_text())
        self.assertFalse(locale['adjustLiveTimezone'])
        self.assertEqual(locale['geoip']['style'], 'none')
        wrapper = (ROOT/'bin/husk-installer-root').read_text()
        self.assertIn('LC_ALL=en_US.UTF-8', wrapper)
        self.assertIn('[ -d /sys/firmware/efi ]', wrapper)


if __name__ == '__main__': unittest.main()
