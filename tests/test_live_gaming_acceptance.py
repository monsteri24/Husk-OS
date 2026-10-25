"""Reject launcher-only, synthetic input, short races and silent audio as gaming proof."""
import ast
import copy
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
HISTORY = '''STK-version:      1.5
History-version:  1
numkarts:         1
numplayers:       1
difficulty:       0
reverse: n
track: lighthouse
model 0: tux
count:     6
1200 0 2 32768
1500 0 1 32768
1560 0 1 0
1620 0 0 32768
1680 0 0 0
1800 0 2 0
History file end.
'''
PROFILE = '''[info   ] IrrDriver: OpenGL version: 4.5
[info   ] IrrDriver: OpenGL renderer: llvmpipe (LLVM 20, 256 bits)
[info   ] Profile: Number of frames: 14400 time 120.000000, Average FPS: 120.000000
[info   ] Profile: Average # drawn nodes           20.000000 k
'''


class LiveGamingAcceptanceTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'scripts/ci-test-v3-live-gaming.py'
        self.assertTrue(path.is_file(), 'Actual game input/audio/3D acceptance needs its own bounded harness')
        spec = importlib.util.spec_from_file_location('gaming_acceptance', path)
        self.harness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.harness)

    def report(self):
        return dict(finished=True, success=True, app_id='net.supertuxkart.SuperTuxKart',
            origin='flathub', deployment_commit='a'*64,
            checks=dict(live_session_active=True, unprivileged_launcher=True,
                initial_app_absent=True, user_install_record=True, trusted_origin=True,
                system_packages_unchanged=True, password_unchanged=True,
                no_system_install=True, no_extra_terminal=True),
            input_history=HISTORY, client=dict(profile_log=PROFILE, profile_exit_code=0,
                audio_streams=[dict(properties={'application.name':'SuperTuxKart'}, mute=False)],
                game_policy=dict(gaming_mode=True, overlay=False)),
            audio_capture=dict(start=10,end=20,
                native_processes=[dict(pid=1900,namespace_pids=[1900,2],uid=1000,elf=True,
                    flatpak_id='net.supertuxkart.SuperTuxKart')],
                observations=[dict(at=second,error=None,other_streams=[],streams=[dict(
                    mute=False,corked=False,properties={'application.name':'SuperTuxKart',
                    'application.process.id':'2'})]) for second in range(10,21)]),
            stability=dict(healthy_seconds=65, samples=60,
                windows=[dict(app_id='supertuxkart', title='SuperTuxKart', minimized=False)],
                processes=[dict(pid=1900, uid=1000, elf=True,
                    flatpak_id='net.supertuxkart.SuperTuxKart', executable='/app/bin/supertuxkart')]),
            available_bytes=900000000)

    def test_input_proof_requires_engine_consumed_human_press_and_release(self):
        actual = self.harness.parse_input_history(HISTORY)
        self.assertTrue(actual['accelerated'])
        self.assertTrue(actual['steered'])
        self.assertEqual(actual['events'], 6)
        for invalid in (HISTORY.replace('numplayers:       1','numplayers:       0'),
                        HISTORY.replace('count:     6','count:     7'),
                        HISTORY.replace('1200 0 2 32768','1200 0 2 0'),
                        HISTORY.replace('1800 0 2 0','1800 0 2 32768'),
                        HISTORY.replace('History file end.',''), 'QMP sent up: OK'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.harness.parse_input_history(invalid)

    def test_profile_requires_real_opengl_and_completed_nonzero_race_statistics(self):
        actual = self.harness.parse_profile_log(PROFILE)
        self.assertEqual(actual['frames'], 14400)
        self.assertEqual(actual['runtime_seconds'], 120)
        self.assertIn('llvmpipe', actual['renderer'])
        for invalid in ('Window appeared', PROFILE.replace('14400','0'),
                        PROFILE.replace('120.000000','nan'),
                        PROFILE.replace('time 120.000000','time 1.000000'),
                        PROFILE.replace('OpenGL version: 4.5','No graphics'),
                        PROFILE.replace('20.000000 k','0.000000 k')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.harness.parse_profile_log(invalid)

    def test_wrapper_window_missing_proof_and_unmeasured_stability_cannot_pass(self):
        report = self.report()
        self.assertEqual(self.harness.validate_gameplay_report(report), [])
        for name in report['checks']:
            invalid=copy.deepcopy(report); invalid['checks'].pop(name)
            self.assertTrue(self.harness.validate_gameplay_report(invalid), name)
        for changes in (dict(finished=False),dict(success=False),dict(origin='unknown'),
                        dict(deployment_commit=''),dict(input_history=''),dict(available_bytes=0)):
            self.assertTrue(self.harness.validate_gameplay_report(dict(report,**changes)))
        for changes in (dict(healthy_seconds=59),dict(healthy_seconds=True),
                        dict(healthy_seconds=math.nan),dict(samples=1),dict(windows=[]),
                        dict(processes=[]),dict(processes=[dict(pid=10,uid=0,elf=True,
                            flatpak_id='net.supertuxkart.SuperTuxKart',executable='/app/bin/supertuxkart')])):
            invalid=copy.deepcopy(report);invalid['stability'].update(changes)
            self.assertTrue(self.harness.validate_gameplay_report(invalid), changes)
        for changes in (dict(profile_exit_code=1),dict(profile_exit_code=False),
                        dict(profile_log=''),dict(audio_streams=[])):
            invalid=copy.deepcopy(report);invalid['client'].update(changes)
            self.assertTrue(self.harness.validate_gameplay_report(invalid), changes)

    def test_audio_acceptance_uses_only_the_measured_game_interval(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'game-audio.wav'
            with wave.open(str(path),'wb') as output:
                output.setparams((2,2,8000,0,'NONE','not compressed'))
                output.writeframes(b'\0'*(8000*4)+struct.pack('<hhhh',1000,1000,-1000,-1000)*8000)
            result=self.harness.summarize_audio(path,44+8000*4,44+8000*4*3)
            self.assertEqual(result['seconds'],2)
            self.assertEqual(result['peak'],1000)
            self.assertEqual(result['rms'],1000)
            self.assertFalse(self.harness.validate_audio(result))
            silent=self.harness.summarize_audio(path,44,44+8000*4)
            self.assertTrue(self.harness.validate_audio(silent))
            with wave.open(str(path),'wb') as output:
                output.setparams((2,2,8000,0,'NONE','not compressed'))
                output.writeframes(struct.pack('<hh',1000,-1000)*(8000*3))
            dc=self.harness.summarize_audio(path,44,44+8000*4*3)
            self.assertTrue(self.harness.validate_audio(dc),
                            'Opposite constant offsets in stereo channels are not varying game audio')
            for start,end in ((0,0),(100,90),(44,45)):
                with self.subTest(start=start,end=end), self.assertRaises(ValueError):
                    self.harness.summarize_audio(path,start,end)

    def test_embedded_game_client_and_observer_compile(self):
        for name in ('GAME_CLIENT','ROOT_OBSERVER'):
            ast.parse('CONFIG={}\n'+getattr(self.harness,name), filename=name)

    def test_gameplay_success_cannot_hide_failed_virtual_audio(self):
        self.assertTrue(hasattr(self.harness,'GamingAcceptance'))
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            with wave.open(str(directory/'game-audio.wav'),'wb') as output:
                output.setparams((2,2,8000,0,'NONE','not compressed'))
                output.writeframes(b'\0'*(8000*4*3))
            acceptance=object.__new__(self.harness.GamingAcceptance)
            acceptance.artifacts=directory;acceptance.password='not-an-account-password'
            acceptance.audio_interval=(44,44+8000*4*3)
            acceptance.result=dict(gameplay='PASSED',live_shutdown='PASSED',problems=[])
            with patch.object(self.harness.auth.AuthorizationAcceptance,'run',return_value=0):
                self.assertEqual(acceptance.run(),1)
            self.assertEqual(acceptance.result['virtual_audio'],'FAILED')

    def test_audio_attribution_cannot_reuse_old_stream_after_disappearance_or_query_failure(self):
        report=self.report()
        self.assertEqual(self.harness.validate_gameplay_report(report),[])
        for changes in (dict(streams=[]),dict(error='pactl failed'),
                        dict(other_streams=[{'application.name':'Other player'}]),
                        dict(streams=[dict(mute=False,corked=False,properties={
                            'application.name':'SuperTuxKart','application.process.id':'999'})])):
            invalid=copy.deepcopy(report)
            invalid['audio_capture']['observations'][5].update(changes)
            with self.subTest(changes=changes):
                self.assertTrue(self.harness.validate_gameplay_report(invalid),
                    'Earlier nonempty audio_streams must not conceal lost capture-time attribution')
        invalid=copy.deepcopy(report)
        invalid['audio_capture']['observations']=invalid['audio_capture']['observations'][:2]
        self.assertTrue(self.harness.validate_gameplay_report(invalid))
