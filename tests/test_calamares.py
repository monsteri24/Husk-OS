import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1] / 'installer/calamares'


class CalamaresIntegrationTests(unittest.TestCase):
    def test_install_sequence_uses_arch_initcpio(self):
        config = yaml.safe_load((ROOT / 'settings.conf').read_text())
        jobs = next(phase['exec'] for phase in config['sequence'] if 'exec' in phase)
        self.assertIn('initcpio', jobs)
        self.assertNotIn('initramfs', jobs)
        self.assertNotIn('initramfscfg', jobs)
        config = yaml.safe_load((ROOT / 'modules/initcpio.conf').read_text())
        self.assertEqual(config['kernel'], 'all')
        self.assertFalse(config['be_unsafe'])

    def test_every_configured_module_has_an_explicit_configuration(self):
        config = yaml.safe_load((ROOT / 'settings.conf').read_text())
        instances = {item['module'] + '@' + item['id']: item['config'] for item in config['instances']}
        for phase in config['sequence']:
            for names in phase.values():
                for name in names:
                    path = ROOT / 'modules' / instances.get(name, name + '.conf')
                    with self.subTest(module=name): self.assertTrue(path.is_file(), str(path))

    def test_machine_ids_and_entropy_are_generated_for_target(self):
        path = ROOT / 'modules/machineid.conf'
        self.assertTrue(path.is_file())
        config = yaml.safe_load(path.read_text())
        self.assertTrue(config['systemd'])
        self.assertTrue(config['dbus'])
        self.assertFalse(config['entropy-copy'])
        self.assertIn('/var/lib/systemd/random-seed', config['entropy-files'])


if __name__ == '__main__': unittest.main()
