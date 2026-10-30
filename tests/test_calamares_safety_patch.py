import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BackendPatchTests(unittest.TestCase):
    def test_patch_requires_and_changes_exact_pinned_source(self):
        path = ROOT / 'scripts/patch-calamares-safety.py'
        self.assertTrue(path.is_file(), 'The pinned backend safety patch is required')
        source = ROOT.parent / 'calamares-3.3.14'
        if not source.is_dir(): self.skipTest('Pinned upstream source not extracted')
        spec = importlib.util.spec_from_file_location('husk_safety_patch',path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'source'; shutil.copytree(source, target)
            mod.apply(target)
            devices = (target / 'src/modules/partition/core/DeviceList.cpp').read_text()
            jobs = (target / 'src/modules/partition/core/PartitionCoreModule.cpp').read_text()
            choices = (target / 'src/modules/partition/gui/ChoicePage.cpp').read_text()
            self.assertIn('HuskDiskGuard::capture', devices)
            self.assertLess(devices.index('HuskDiskGuard::beginScan'),devices.index('backend->scanDevices'))
            self.assertIn('new HuskDiskGuardJob', jobs)
            self.assertLess(jobs.index('new HuskDiskGuardJob'), jobs.index('new AutoMountManagementJob'))
            self.assertIn('new HuskDiskGuardJob( info->device.data()->deviceNode() ) );\n        }\n        lst << info->jobs();',jobs)
            unmount=(target/'src/modules/umount/UmountJob.cpp').read_text()
            self.assertNotIn('{ "-lv" }',unmount)
            self.assertIn('Select Installation Drive', choices)
            self.assertIn('m_drivesCombo->setCurrentIndex( -1 )', choices)
            self.assertIn('force_uncheck( m_grp, m_alongsideButton ); // Husk erase-only', choices)
            with self.assertRaises(ValueError): mod.apply(target)


if __name__ == '__main__': unittest.main()
