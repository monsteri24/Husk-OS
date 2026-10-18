import importlib.util
import unittest
from types import SimpleNamespace


@unittest.skipUnless(importlib.util.find_spec('gi'), 'GTK Python bindings unavailable')
class InstallerProcessOutcomeTests(unittest.TestCase):
    def test_nonzero_backend_exit_keeps_a_diagnostic_visible(self):
        from ownos.ui.installer import InstallerLauncher
        for code in (1, 2, -6, 126, 127):
            events=[]
            window = SimpleNamespace(closed=False, failed=lambda message:events.append(('failure',message)),
                                     destroy=lambda:events.append(('destroy',None)))
            InstallerLauncher.finished(window,code)
            self.assertEqual(events[0][0],'failure')
            self.assertTrue(events[0][1])

    def test_zero_backend_exit_closes_without_claiming_installation_success(self):
        from ownos.ui.installer import InstallerLauncher
        events=[]
        window=SimpleNamespace(closed=False,failed=lambda message:events.append(message),
                               destroy=lambda:events.append('closed'))
        InstallerLauncher.finished(window,0)
        self.assertEqual(events,['closed'])
