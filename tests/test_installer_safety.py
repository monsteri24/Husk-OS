import copy
import unittest

from ownos import installer_safety as safety


def disk(name, major, **kw):
    return dict(name='/dev/' + name, type='disk', size=64 * 1024**3,
                ro=False, rm=False, tran='virtio', model='Disposable VM disk',
                serial=name, wwn='', **{'maj:min': major, 'disk-seq': 100 if name == 'sda' else 101}, children=[], **kw)


class InstallerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.usb = disk('sda', '8:0')
        self.usb['children'] = [dict(name='/dev/sda1', type='part', size=2*1024**3,
             **{'maj:min':'8:1'}, mountpoints=['/run/archiso/bootmnt'], fstype='iso9660')]
        self.target = disk('vda', '254:0')
        self.data = {'blockdevices':[self.usb, self.target]}

    def test_live_child_protects_whole_source_device(self):
        result = safety.inventory(self.data, '8:1')
        self.assertEqual([d['name'] for d in result], ['/dev/vda'])

    def test_unknown_or_ambiguous_source_fails_closed(self):
        for source in ('', '9:9'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                safety.inventory(self.data, source)
        self.data['blockdevices'].append(copy.deepcopy(self.usb))
        with self.assertRaises(ValueError): safety.inventory(self.data, '8:1')

    def test_read_only_removable_mounted_and_raid_targets_are_rejected(self):
        for change in ({'ro':True}, {'rm':True}, {'type':'raid1'},
                       {'mountpoints':['/mnt/user-data']}, {'fstype':'linux_raid_member'}):
            with self.subTest(change=change):
                target = dict(self.target, **change)
                self.assertEqual(safety.inventory({'blockdevices':[self.usb,target]}, '8:1'), [])

    def test_mounted_children_and_swap_are_rejected(self):
        for mount in ('/mnt/data', '[SWAP]'):
            target = copy.deepcopy(self.target)
            target['children'] = [dict(name='/dev/vda1', type='part', mountpoints=[mount])]
            self.assertEqual(safety.inventory({'blockdevices':[self.usb,target]}, '8:1'), [])

    def test_snapshot_changes_on_device_identity_or_partitions(self):
        original = safety.fingerprint(self.target)
        changed = copy.deepcopy(self.target); changed['serial'] = 'replacement'
        self.assertNotEqual(original, safety.fingerprint(changed))
        changed = copy.deepcopy(self.target); changed['children'] = [{'name':'/dev/vda1','size':10}]
        self.assertNotEqual(original, safety.fingerprint(changed))

    def test_no_disk_name_prefix_matching(self):
        data = {'blockdevices':[self.usb, disk('sdaa','65:0')]}
        self.assertEqual([d['name'] for d in safety.inventory(data,'8:1')], ['/dev/sdaa'])

    def test_missing_disk_sequence_is_ambiguous_and_replacement_is_rejected(self):
        target = dict(self.target); target.pop('disk-seq')
        self.assertEqual(safety.inventory({'blockdevices':[self.usb,target]},'8:1'),[])
        self.target['serial'] = ''; self.target['wwn'] = ''
        token = safety.fingerprint(self.target)
        self.target['disk-seq'] += 1
        with self.assertRaises(ValueError): safety.verify(self.data,'8:1','/dev/vda',token)

    def test_verification_rejects_source_change_or_replaced_device(self):
        token = safety.fingerprint(self.target)
        self.assertTrue(safety.verify(self.data, '8:1', '/dev/vda', token))
        with self.assertRaises(ValueError): safety.verify(self.data, '254:0','/dev/vda',token)
        self.target['size'] += 4096
        with self.assertRaises(ValueError): safety.verify(self.data,'8:1','/dev/vda',token)


if __name__ == '__main__': unittest.main()
