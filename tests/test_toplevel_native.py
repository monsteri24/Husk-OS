"""Exercise native state decoding and its JSON wire contract with real C."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('wayland-scanner') and shutil.which('pkg-config'),
                     'Native state test needs Wayland development tools')
class NativeToplevelStateTests(unittest.TestCase):
    def messages(self, body):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            protocol = ROOT / 'native/protocols/wlr-foreign-toplevel-management-unstable-v1.xml'
            for mode, destination in [('client-header', 'foreign-toplevel-client-protocol.h'),
                                      ('private-code', 'foreign-toplevel-protocol.c')]:
                subprocess.run(['wayland-scanner', mode, str(protocol), str(path / destination)], check=True)
            source = path / 'state.c'
            source.write_text('''#define main bridge_main
#include "''' + str(ROOT / 'native/toplevel.c') + '''"
#undef main
int main(void) {
''' + body + '''
    return 0;
}
''')
            cflags = subprocess.check_output(['pkg-config', '--cflags', 'wayland-client'], text=True).split()
            libs = subprocess.check_output(['pkg-config', '--libs', 'wayland-client'], text=True).split()
            executable = path / 'state'
            result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', *cflags,
                '-I' + str(ROOT / 'native'), '-I' + str(path), str(source),
                str(path / 'foreign-toplevel-protocol.c'), *libs, '-o', str(executable)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return [json.loads(line) for line in subprocess.check_output([str(executable)], text=True).splitlines()]

    def test_native_maximized_and_fullscreen_state_is_reset_on_each_event(self):
        messages = self.messages('''
    struct entry e = {.id = 7, .title = "game", .app_id = "test"};
    uint32_t flags[] = {ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_ACTIVATED,
                       ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_MAXIMIZED,
                       ZWLR_FOREIGN_TOPLEVEL_HANDLE_V1_STATE_FULLSCREEN};
    struct wl_array states = {.size = sizeof(flags), .alloc = sizeof(flags), .data = flags};
    state(&e, NULL, &states); done(&e, NULL);
    states.size = 0;
    state(&e, NULL, &states); done(&e, NULL);
''')
        self.assertEqual([(message.get('maximized'), message.get('fullscreen')) for message in messages],
                         [(True, True), (False, False)])

    def test_native_output_enter_leave_and_rotation_update_the_wire_identity(self):
        messages = self.messages('''
    struct output_info info = {.handle = (struct wl_output *)(uintptr_t)1, .name = "DP-1",
        .x = 1920, .y = 0, .width = 3840, .height = 2160, .scale = 2};
    output_infos = &info;
    struct entry e = {.id = 7, .title = "game", .app_id = "test"};
    entries = &e;
    output_enter(&e, NULL, info.handle);
    output_enter(&e, NULL, info.handle);
    done(&e, NULL);
    info.transform = WL_OUTPUT_TRANSFORM_90;
    output_done(&info, info.handle);
    output_leave(&e, NULL, info.handle);
    done(&e, NULL);
''')
        self.assertEqual([message['outputs'] for message in messages], [
            [dict(name='DP-1', x=1920, y=0, width=1920, height=1080)],
            [dict(name='DP-1', x=1920, y=0, width=1080, height=1920)], []])


if __name__ == '__main__':
    unittest.main()
