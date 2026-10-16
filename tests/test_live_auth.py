"""Live package admin must authenticate a usable, deliberately set identity."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is needed to exercise the polkit JavaScript rules')
class LiveAuthenticationPolicyTests(unittest.TestCase):
    def evaluate(self, action='org.ownos.admin', user='live', local=True, active=True, wheel=True):
        program = '''
const fs = require('fs'), vm = require('vm');
const admin = [], authorizers = [];
const polkit = {addAdminRule: f => admin.push(f), addRule: f => authorizers.push(f),
                Result: {YES: 'YES'}};
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {polkit});
const input = JSON.parse(process.argv[2]);
const subject = {...input.subject, isInGroup: group => group === 'wheel' && input.wheel};
const invoke = rules => rules.map(f => f({id: input.action}, subject)).filter(v => v !== undefined);
console.log(JSON.stringify({identities: invoke(admin), authorizations: invoke(authorizers)}));
'''
        result = subprocess.run(['node', '-e', program, str(ROOT / 'installer/49-ownos-live.rules'),
                                 json.dumps(dict(action=action, subject=dict(user=user, local=local, active=active),
                                                 wheel=wheel))], capture_output=True, text=True, timeout=8, check=True)
        return json.loads(result.stdout)

    def test_live_native_install_authenticates_live_without_granting_the_action(self):
        result = self.evaluate()
        self.assertEqual(result['identities'], [['unix-user:live']])
        self.assertEqual(result['authorizations'], [])
        policy = ET.parse(ROOT / 'data/org.ownos.admin.policy').find('action')
        self.assertEqual(policy.findtext('defaults/allow_active'), 'auth_admin')
        self.assertEqual(policy.findtext('defaults/allow_inactive'), 'no')
        self.assertEqual(policy.findtext('defaults/allow_any'), 'no')

    def test_other_users_sessions_and_actions_do_not_gain_a_live_identity(self):
        for choice in (dict(user='other'), dict(local=False), dict(active=False), dict(wheel=False),
                       dict(action='org.example.unrelated')):
            with self.subTest(choice=choice):
                result = self.evaluate(**choice)
                self.assertEqual(result['identities'], [])
                self.assertEqual(result['authorizations'], [])

    def test_graphical_installer_has_no_passwordless_live_override(self):
        result = self.evaluate(action='org.ownos.install')
        self.assertEqual(result['authorizations'], [])
        policy = ET.parse(ROOT / 'installer/org.ownos.install.policy').find('action')
        self.assertIn(policy.findtext('defaults/allow_active'), ('auth_admin', 'auth_admin_keep'))


if __name__ == '__main__':
    unittest.main()
