"""Run prepare() with makepkg's real local-source symlink layout."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get('CALAMARES_SOURCE_DIR', ROOT.parent/'calamares-3.3.14'))


class CalamaresPackageTests(unittest.TestCase):
    def test_prepare_uses_verified_regular_assets_when_srcdir_contains_links(self):
        if not (UPSTREAM/'CMakeLists.txt').is_file():
            self.skipTest('Pinned Calamares source fixture unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            start = Path(temporary)
            source = start/'src'; source.mkdir()
            shutil.copytree(UPSTREAM, source/'calamares-3.3.14')
            for name in ('HuskDiskGuard.h','HuskClockSelector.h','husk-finished.qml'):
                shutil.copyfile(ROOT/'packaging/calamares'/name, start/name)
                (source/name).symlink_to(start/name)
            for name in ('patch-calamares-safety.py','patch-calamares-ui.py'):
                shutil.copyfile(ROOT/'scripts'/name, start/name)
                (source/name).symlink_to(start/name)
            result = subprocess.run(['bash','-eu','-c',
                'startdir="$1"; srcdir="$2"; cd "$srcdir"; source "$3"; prepare',
                'prepare-test',str(start),str(source),str(ROOT/'packaging/calamares/PKGBUILD')],
                capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue((source/'calamares-3.3.14/src/modules/locale/HuskClockSelector.h').is_file())
            self.assertIn('HuskDiskGuard::beginScan()',
                (source/'calamares-3.3.14/src/modules/partition/core/DeviceList.cpp').read_text())


if __name__ == '__main__': unittest.main()
