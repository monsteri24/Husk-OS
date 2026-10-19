import importlib.util
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch


@unittest.skipUnless(importlib.util.find_spec('gi'), 'GTK Python bindings unavailable')
class InstallerProcessOutcomeTests(unittest.TestCase):
    def test_authorization_keeps_the_private_display_alive_until_the_fixed_helper_exits(self):
        from ownos.ui import installer
        events=[]
        @contextmanager
        def display():
            events.append('display-ready')
            yield dict(DISPLAY=':2',XAUTHORITY='/private/authority')
            events.append('display-cleaned')
        process=SimpleNamespace(wait=lambda: events.append('process-exited') or 126)
        def spawn(argv, **kwargs):
            self.assertEqual(events,['display-ready'])
            self.assertEqual(argv,['/usr/bin/pkexec','/usr/lib/ownos/husk-installer-root'])
            self.assertEqual(kwargs['env']['XAUTHORITY'],'/private/authority')
            return process
        window=SimpleNamespace(closed=False,open=Mock(),cancel=Mock(),status=Mock(),
                               finished=Mock(),failed=Mock())
        with patch.object(installer,'installer_display_environment',display), \
             patch.object(installer.subprocess,'Popen',side_effect=spawn), \
             patch.object(installer.threading,'Thread',side_effect=lambda target,daemon: SimpleNamespace(start=target)), \
             patch.object(installer.GLib,'idle_add') as idle:
            installer.InstallerLauncher.authorize(window)
        self.assertEqual(events,['display-ready','process-exited','display-cleaned'])
        idle.assert_called_once_with(window.finished,126)

    def test_display_failure_does_not_launch_a_privileged_process(self):
        from ownos.ui import installer
        window=SimpleNamespace(closed=False,open=Mock(),cancel=Mock(),status=Mock(),
                               finished=Mock(),failed=Mock())
        with patch.object(installer,'installer_display_environment',
                side_effect=installer.DisplayAuthorizationError('Display unavailable')), \
             patch.object(installer.subprocess,'Popen') as spawn, \
             patch.object(installer.threading,'Thread',side_effect=lambda target,daemon: SimpleNamespace(start=target)), \
             patch.object(installer.GLib,'idle_add') as idle:
            installer.InstallerLauncher.authorize(window)
        self.assertFalse(spawn.called)
        idle.assert_called_once_with(window.failed,'Display unavailable')

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
