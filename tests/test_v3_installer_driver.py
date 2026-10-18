"""Compile the separate Qt fixture and prove it refuses an ordinary host app.

These are fixture safety tests, never installation or VM acceptance results.
"""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallerDriverSafetyTests(unittest.TestCase):
    def test_driver_is_inert_without_opt_in_and_refuses_an_unmarked_process(self):
        source = ROOT/'scripts/v3-installer-driver.cpp'
        self.assertTrue(source.is_file(), 'The test-only Qt input fixture is missing')
        if not shutil.which('pkg-config') or not shutil.which('c++'):
            self.skipTest('Qt6 C++ development tools are unavailable')
        flags = subprocess.run(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test','Qt6Quick'],
                               capture_output=True,text=True)
        if flags.returncode: self.skipTest('Qt6 Widgets/Test/Quick development packages are unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            driver=directory/'driver.so'
            result=subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fPIC','-shared',
                str(source),'-o',str(driver),*shlex.split(flags.stdout)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            app_source=directory/'app.cpp'
            app_source.write_text('#include <QApplication>\n#include <QTimer>\n'
                'int main(int argc,char** argv) { QApplication app(argc,argv); '
                'QTimer::singleShot(1700,&app,&QCoreApplication::quit); return app.exec(); }\n')
            app=directory/'app'
            result=subprocess.run(['c++','-std=c++17','-fPIC',str(app_source),'-o',str(app),
                *shlex.split(flags.stdout)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            log=directory/'events.jsonl'
            environment=dict(os.environ,LD_PRELOAD=str(driver),QT_QPA_PLATFORM='offscreen',
                QT_QUICK_BACKEND='software',HUSK_INSTALL_DRIVER_LOG=str(log),
                HUSK_INSTALL_TEST_USER='huskcheck',HUSK_INSTALL_TEST_PASSWORD='DisposableTestSecret732')
            if environment.get('HUSK_TEST_SYSROOT'):
                prefix=Path(environment['HUSK_TEST_SYSROOT'])/'usr/lib/x86_64-linux-gnu/qt6'
                environment['QT_PLUGIN_PATH']=str(prefix/'plugins')
            environment.pop('HUSK_INSTALL_ACCEPTANCE',None)
            result=subprocess.run([str(app)],env=environment,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertFalse(log.exists(), 'An ordinary Qt process must not start automation')
            environment['HUSK_INSTALL_ACCEPTANCE']='1'
            result=subprocess.run([str(app)],env=environment,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,85,result.stdout+result.stderr)
            events=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([event['event'] for event in events],['driver-failed'])
            self.assertIn('marked disposable UEFI Live guest',events[0]['message'])


if __name__ == '__main__':
    unittest.main()
