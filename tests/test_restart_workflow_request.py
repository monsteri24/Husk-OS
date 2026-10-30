"""Execute the real workflow's bounded completion-mode selection."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT=Path(__file__).resolve().parents[1]

class RestartRequestTests(unittest.TestCase):
    def test_workflow_runs_only_requested_validated_completion_modes(self):
        workflow=yaml.load((ROOT/'.github/workflows/v3-restart-acceptance.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertIn('request',workflow['jobs'],'A passed Now scenario must not be repeated for an automatic-only correction')
        script=workflow['jobs']['request']['steps'][1]['run']
        source=script.split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'.github').mkdir();output=root/'output.txt'
            for modes,expected in ((None,['now','automatic']),(['automatic'],['automatic']),(['now'],['now']),
                                   ([],None),(['automatic','automatic'],None),(['unknown'],None),('now',None)):
                request={} if modes is None else dict(modes=modes)
                (root/'.github/v3-restart-request.json').write_text(json.dumps(request));output.write_text('')
                result=subprocess.run(['/usr/bin/python3','-c',source],cwd=root,
                    env=dict(os.environ,GITHUB_OUTPUT=str(output)),capture_output=True,text=True)
                with self.subTest(modes=modes):
                    if expected is None:
                        self.assertNotEqual(result.returncode,0)
                        self.assertEqual(output.read_text(),'')
                    else:
                        self.assertEqual(result.returncode,0,result.stderr)
                        self.assertEqual(json.loads(output.read_text().removeprefix('modes=').strip()),expected)

if __name__=='__main__': unittest.main()
