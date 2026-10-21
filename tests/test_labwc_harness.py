import importlib.util
import ast
import gc
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import weakref


class LabwcHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'scripts/test-labwc.py'
        spec = importlib.util.spec_from_file_location('husk_labwc_harness', path)
        harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(harness)
        cls.harness = harness

    def observer_registration(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/labwc-test-observer/sitecustomize.py'
        functions = [node for node in ast.walk(ast.parse(path.read_text()))
                     if isinstance(node,ast.FunctionDef) and node.name == 'observe_widget']
        self.assertEqual(len(functions),1,'The observer must track native GTK identities until destroy')
        namespace=dict(observed=set(),observe_input=Mock(return_value=False))
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<observer-registration>','exec'),namespace)
        return namespace

    def test_native_observer_identity_survives_wrapper_gc_without_duplicate_handlers(self):
        observer = self.observer_registration()
        class Native:
            def __init__(self): self.handlers={}
        class Widget:
            def __init__(self,native): self.native=native
            def __hash__(self): return 17429
            def connect(self,signal,callback,*args): self.native.handlers.setdefault(signal,[]).append((callback,args))
            def destroy(self):
                for callback,args in self.native.handlers.get('destroy',[]): callback(self,*args)
        native=Native(); widget=Widget(native); reference=weakref.ref(widget)
        self.assertTrue(observer['observe_widget'](widget,'test-window'))
        del widget; gc.collect()
        self.assertIsNone(reference(),'Passive observation must not retain a dead Python wrapper')
        replacement=Widget(native)
        self.assertFalse(observer['observe_widget'](replacement,'test-window'))
        self.assertEqual(len(native.handlers['event']),1)
        replacement.destroy()
        self.assertEqual(observer['observed'],set())

    @unittest.skipUnless(os.environ.get('OWNOS_UI_TESTS') == '1','Needs real GTK widget ownership')
    def test_real_gtk_owned_widget_is_observed_once_and_released_at_destroy(self):
        from ownos.ui.common import Gtk,Gdk
        observer=self.observer_registration()
        box=Gtk.Box(); widget=Gtk.Button(label='Task observation test'); box.add(widget)
        self.assertTrue(observer['observe_widget'](widget,'test-window'))
        identity=hash(widget); del widget; gc.collect()
        widget=box.get_children()[0]
        self.assertEqual(hash(widget),identity)
        self.assertFalse(observer['observe_widget'](widget,'test-window'))
        widget.emit('event',Gdk.Event.new(Gdk.EventType.BUTTON_RELEASE))
        self.assertEqual(observer['observe_input'].call_count,1)
        widget.destroy(); box.destroy()
        self.assertEqual(observer['observed'],set())

    def test_task_click_waits_for_fresh_actual_panel_focus_and_button_hover(self):
        test=self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        button=dict(tooltip='Husk Files',rect=[743,746,43,54],mapped=True,hovered=False)
        state=dict(sequence=1,pointer_window_title='Husk Files',task_buttons=[button])
        test.state=lambda:state
        test.pointer_event=Mock()
        def wait(description,predicate):
            if description.endswith('mapped task button'): return predicate()
            self.assertIsNone(predicate())
            state['sequence']=2; button['hovered']=True
            self.assertIsNone(predicate(),'A different focused surface must not receive a task click')
            state['sequence']=3; state['pointer_window_title']='Husk Taskbar'; button['hovered']=False
            self.assertIsNone(predicate(),'A panel enter alone does not mean the target GTK button has hover')
            state['sequence']=4; button['hovered']=True
            return predicate()
        test.wait=wait
        self.assertEqual(test.wait_task_hover('Husk Files','files'),button)
        test.pointer_event.assert_called_once_with('move',button['rect'])

    def test_missing_app_waits_for_actual_cancel_focus_after_mapping(self):
        test=self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        window=dict(confirmation=dict(primary_text='Install Firefox?',cancel_focused=False,
                                      cancel_default=True,confirm_focused=False))
        test.search_start=Mock(return_value=dict(rect=[0,0,200,40]))
        test.click=Mock();test.confirmation=lambda:window
        test.state=lambda:dict(start_mapped=False)
        def wait(description,predicate):
            if description.startswith('Start hides'): return predicate()
            self.assertIsNone(predicate(),'A mapped dialog may precede its compositor focus event')
            window['confirmation']['cancel_focused']=True
            return predicate()
        test.wait=wait
        self.assertIs(test.firefox_confirmation(),window)

    def test_output_discovery_accepts_a_visible_window_without_name_or_class(self):
        tree = '''xwininfo: Window id: 0x50d (the root window) (has no name)
  Root window id: 0x50d (the root window) (has no name)
  2 children:
  0x400001 (has no name): ()  1024x768+0+0  +0+0
  0x400002 "tiny helper": ()  1x1+0+0  +0+0
'''
        self.assertEqual(self.harness.output_candidates(tree), ['0x400001'])

    def test_rendered_active_decoration_excludes_inactive_and_scattered_pixels(self):
        class Raster:
            width, height = 600, 90

            def load(self):
                return self

            def __getitem__(self, point):
                x, y = point
                if 80 <= x < 380 and 12 <= y < 38:
                    return (28, 48, 76)
                if 400 <= x < 590 and 50 <= y < 75:
                    return (22, 32, 51)  # The shipped inactive decoration.
                if x == 30 and y == 80:
                    return (28, 48, 76)
                return (0, 0, 0)

        self.assertEqual(self.harness.active_decoration_bounds(Raster()), [80, 12, 300, 26])

    def test_a_missing_rendered_decoration_cannot_guess_an_input_target(self):
        class Raster:
            width, height = 300, 100

            def load(self):
                return self

            def __getitem__(self, point):
                return (0, 0, 0)

        with self.assertRaisesRegex(AssertionError, 'No rendered'):
            self.harness.active_decoration_bounds(Raster())

    def test_widget_target_uses_the_rendered_decoration_and_relative_allocation(self):
        self.assertEqual(self.harness.client_widget_rectangle(
            [100, 50, 852, 30], [850, 560], [10, 20, 112, 36]), [111, 101, 112, 36])

    def test_a_different_window_width_is_rejected_before_sending_input(self):
        with self.assertRaisesRegex(AssertionError, 'does not match'):
            self.harness.client_widget_rectangle([10, 10, 900, 30], [460, 300], [20, 20, 112, 36])

    def test_missing_or_clipped_widget_allocations_cannot_receive_input(self):
        for allocation in (None, [-1, 10, 112, 36], [400, 10, 112, 36],
                           [10, 290, 112, 36], [10, 10, 0, 36]):
            with self.subTest(allocation=allocation), self.assertRaises(AssertionError):
                self.harness.client_widget_rectangle([10, 10, 460, 30], [460, 300], allocation)

    def test_same_position_row_clicks_and_pointer_moves_do_not_wait_for_motion(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        test.output = '0x200004'
        commands = []
        test.command = lambda argv: commands.append(argv)
        with tempfile.TemporaryDirectory() as directory, patch.object(self.harness.time, 'sleep'):
            test.artifacts = Path(directory)
            row = [240, 188, 800, 40]
            test.click(row)
            test.click(row)
            test.pointer_event('move', row)
            test.pointer_event('move', row)
        self.assertEqual(len(commands), 4)
        for command in commands:
            self.assertEqual(command[:2], ['xdotool', 'mousemove'])
            self.assertNotIn('--sync', command)
            self.assertEqual(command[command.index('--window') + 1:][:3], ['0x200004', '640', '208'])
        self.assertEqual(commands[0][-2:], ['click', '1'])
        self.assertEqual(commands[1][-2:], ['click', '1'])

    def test_native_context_and_double_clicks_record_the_actual_pointer_buttons(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        test.output = '0x200004'; commands = []
        test.command = lambda argv: commands.append(argv)
        with tempfile.TemporaryDirectory() as directory, patch.object(self.harness.time, 'sleep'):
            test.artifacts = Path(directory)
            test.click([900, 200, 1, 1], button=3)
            test.click([240, 188, 800, 40], count=2)
            import json
            events = [json.loads(line) for line in (test.artifacts / 'input-events.jsonl').read_text().splitlines()]
        self.assertEqual(commands[0][-2:], ['click', '3'])
        self.assertEqual(commands[1][-6:], ['click', '--repeat', '2', '--delay', '90', '1'])
        self.assertEqual([(event['button'], event['count']) for event in events], [(3, 1), (1, 2)])

    def test_cancel_guard_detects_a_graphical_installer_as_a_side_effect(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        test.entries = lambda: []
        test.installer_terminals = lambda: []
        test.state = lambda: dict(windows=[dict(app_install=dict(appid='firefox',state='checking'))])
        with patch.object(self.harness.time,'sleep'), self.assertRaisesRegex(AssertionError,'graphical'):
            test.assert_no_installer(set(),'Cancel')

    def test_native_buttons_must_finish_reallocation_before_input(self):
        test=self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        window=dict(id='installer',mapped=True,size=[640,470],buttons=[dict(label='Close',rect=[361,402,65,44])])
        state=dict(sequence=1,windows=[window]); test.state=lambda kind='desktop':state
        def wait(description,predicate):
            self.assertIsNone(predicate())
            state['sequence']=2; self.assertIsNone(predicate())
            window['size']=[640,472]; window['buttons'][0]['rect']=[490,404,58,44]
            for seq in (3,4):
                state['sequence']=seq; self.assertIsNone(predicate())
            # Rereading a sample does not count toward stable observations.
            self.assertIsNone(predicate())
            state['sequence']=5
            return predicate()
        test.wait=wait
        result=test.wait_stable_window('desktop',lambda candidate:True,'actual Close allocation')
        self.assertEqual(result['buttons'][0]['rect'],[490,404,58,44])

    def test_reopening_same_query_keeps_text_and_waits_for_fresh_stable_row(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        current = dict(sequence=40, panel_buttons=[dict(tooltip='Start', rect=[0, 0, 40, 40])],
                       start_mapped=True, start=[0, 0, 510, 540], search=[20, 50, 460, 50],
                       search_text='Firefox', rows=[dict(name='Firefox', identity='old', rect=[20, 110, 460, 48])])
        test.state = lambda: current
        test.click = lambda rectangle: None
        test.key = lambda key: self.fail('An unchanged query must not be rewritten')
        test.type_text = lambda text: self.fail('An unchanged query must not be rewritten')

        def wait(description, predicate):
            if description.startswith('Start mapped'):
                return predicate()
            # An old sample cannot count. A replacement row resets stability,
            # and rereading the same observer sample cannot advance it.
            for sequence, identity in [(40, 'old'), (41, 'old'), (42, 'new'), (42, 'new'), (43, 'new')]:
                current['sequence'] = sequence
                current['rows'][0]['identity'] = identity
                self.assertIsNone(predicate())
            current['sequence'] = 44
            return predicate()

        test.wait = wait
        row = test.search_start('Firefox')
        self.assertEqual(row['identity'], 'new')

    def test_search_result_rejects_unallocated_one_pixel_rows(self):
        test = self.harness.DesktopTest.__new__(self.harness.DesktopTest)
        current = dict(sequence=1, panel_buttons=[dict(tooltip='Start', rect=[0, 0, 40, 40])],
                       start_mapped=True, start=[385, 180, 510, 540], search=[406, 254, 468, 50],
                       search_text='Terminal', rows=[dict(name='Terminal', identity='new', rect=[405, 317, 1, 1])])
        test.state = lambda: current
        test.click = lambda rectangle: None
        test.key = lambda key: self.fail('The matching query is already typed')
        test.type_text = lambda text: self.fail('The matching query is already typed')
        def wait(description, predicate):
            if description.startswith('Start mapped'): return predicate()
            for sequence in (2, 3, 4, 5):
                current['sequence'] = sequence
                self.assertIsNone(predicate(), 'A stable 1×1 GTK allocation is not a clickable row')
            current['rows'][0]['rect'] = [406, 318, 468, 48]
            for sequence in (6, 7):
                current['sequence'] = sequence
                self.assertIsNone(predicate())
            current['sequence'] = 8
            return predicate()
        test.wait = wait
        self.assertEqual(test.search_start('Terminal')['rect'], [406, 318, 468, 48])
