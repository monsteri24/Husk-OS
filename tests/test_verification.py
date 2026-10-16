import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class VerificationEvidenceTests(unittest.TestCase):
    def test_existing_evidence_is_rejected_before_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, 'scripts/verify-five.py', '--output', directory], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Evidence output already exists', result.stderr)
            self.assertEqual(list(Path(directory).iterdir()), [])
