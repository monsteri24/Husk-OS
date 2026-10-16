import tempfile
import unittest
from pathlib import Path


class VMTests(unittest.TestCase):
    def setUp(self):
        try:
            from ownos import vm
            self.vm = vm
        except ImportError as exc: self.fail('Safe VM runner is missing: ' + str(exc))

    def test_qemu_attaches_only_explicit_virtual_disk_and_iso(self):
        command = self.vm.qemu_command(Path('/tmp/ownos.iso'), Path('/tmp/ownos.qcow2'),
                                       Path('/tmp/OVMF_CODE.fd'), Path('/tmp/vars.fd'), kvm=False)
        self.assertIn('tcg', command)
        self.assertIn('/tmp/ownos.iso', command)
        self.assertIn('file=/tmp/ownos.qcow2,if=virtio,format=qcow2', command)
        self.assertFalse(any('/dev/sd' in value or '/dev/nvme' in value for value in command))

    def test_physical_disk_and_qemu_option_injection_are_rejected(self):
        for path in ['/dev/sda','/dev/nvme0n1','/tmp/test.qcow2,format=raw','/tmp/test.raw']:
            with self.subTest(path=path), self.assertRaises(ValueError): self.vm.validate_disk(Path(path))

    def test_symlink_disk_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / 'disk.qcow2'; link.symlink_to('/dev/null')
            with self.assertRaises(ValueError): self.vm.validate_disk(link)

    def test_external_data_files_and_backing_files_are_rejected(self):
        validator = getattr(self.vm, 'validate_image_info', None)
        self.assertIsNotNone(validator, 'qcow2 metadata must be checked before launch')
        for info in [dict(format='qcow2', **{'backing-filename': '/tmp/other'}),
                     {'format':'qcow2','format-specific':{'data':{'data-file':'/tmp/other'}}},
                     {'format':'qcow2','format-specific':{'data':{'data-file-raw':True}}},
                     [], {'format':'raw'}, {'format':'qcow2','format-specific':{'data':[]}}]:
            with self.subTest(info=info), self.assertRaises(ValueError): validator(info)

    def test_standalone_qcow2_metadata_is_accepted(self):
        validator = getattr(self.vm, 'validate_image_info', None)
        self.assertIsNotNone(validator)
        validator({'format':'qcow2','format-specific':{'type':'qcow2','data':{'compat':'1.1'}}})

    def test_firmware_variables_must_be_regular_files(self):
        validator = getattr(self.vm, 'validate_vars_file', None)
        self.assertIsNotNone(validator)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'vars.fd'; folder.mkdir()
            with self.assertRaises(ValueError): validator(folder)


if __name__ == '__main__': unittest.main()
