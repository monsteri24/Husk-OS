#!/usr/bin/env python3
"""Apply the small erase-only Husk integration to the reviewed Calamares source.

All partitioning is still performed by upstream Calamares/KPMCore. Exact
replacement counts deliberately fail builds when upgrading the backend.
"""
import argparse
from pathlib import Path


def replace(text, old, new):
    if text.count(old) != 1: raise ValueError('Calamares source differs at: ' + old[:90])
    return text.replace(old, new, 1)


def apply(source, assets=None):
    source = Path(source)
    assets = Path(assets) if assets else Path(__file__).resolve().parents[1] / 'packaging/calamares'
    base = source / 'src/modules/partition'
    paths = {n:base / n for n in ('core/DeviceList.cpp','core/PartitionCoreModule.cpp','gui/ChoicePage.cpp')}
    texts = {n:p.read_text() for n,p in paths.items()}
    devices = texts['core/DeviceList.cpp']
    devices = replace(devices, '#include "DeviceList.h"', '#include "DeviceList.h"\n#include "HuskDiskGuard.h"')
    devices = replace(devices,
        '    DeviceList devices = backend->scanDevices( /* not includeReadOnly, not includeLoopback */ ScanFlag( 0 ) );',
        '    if ( which == DeviceType::WritableOnly ) HuskDiskGuard::beginScan();\n'
        '    DeviceList devices = backend->scanDevices( /* not includeReadOnly, not includeLoopback */ ScanFlag( 0 ) );')
    devices = replace(devices, 'else if ( writableOnly && hasRootPartition( *it ) )',
        'else if ( writableOnly && !HuskDiskGuard::capture( ( *it )->deviceNode() ) )\n'
        '        {\n            it = removeInAllModes( devices, it );\n        }\n'
        '        else if ( writableOnly && hasRootPartition( *it ) )')
    jobs = texts['core/PartitionCoreModule.cpp']
    jobs = replace(jobs, '#include "core/PartitionCoreModule.h"', '#include "core/PartitionCoreModule.h"\n#include "HuskDiskGuard.h"')
    old = '    Calamares::job_ptr automountControl( new AutoMountManagementJob( true /* disable automount */ ) );'
    jobs = replace(jobs, old, '''    // Recheck every changed target before any unmount or queued disk writes.
    for ( const auto* info : m_deviceInfos )
    {
        if ( info->isDirty() )
            lst << Calamares::job_ptr( new HuskDiskGuardJob( info->device.data()->deviceNode() ) );
    }
''' + old)
    jobs = replace(jobs, '        lst << info->jobs();',
        '        if ( info->isDirty() )\n        {\n'
        '            lst << Calamares::job_ptr( new HuskDiskGuardJob( info->device.data()->deviceNode() ) );\n'
        '        }\n        lst << info->jobs();')
    choices = texts['gui/ChoicePage.cpp']
    choices = replace(choices, 'm_drivesLabel->setText( tr( "Select storage de&vice:", "@label" ) );',
        'm_drivesLabel->setText( QStringLiteral("Select Installation Drive") );\n'
        '    m_drivesLabel->setAlignment( Qt::AlignCenter );')
    choices = replace(choices, '    setModelToComboBox( m_drivesCombo, core->deviceModel() );\n\n    connect(',
        '    setModelToComboBox( m_drivesCombo, core->deviceModel() );\n'
        '    m_drivesCombo->setPlaceholderText( QStringLiteral("Choose a drive — all data on it will be erased") );\n'
        '    m_drivesCombo->setCurrentIndex( -1 );\n\n    connect(')
    choices = replace(choices,
        '    if ( m_somethingElseButton->isHidden() && m_alongsideButton->isHidden() && m_replaceButton->isHidden()\n',
        '    force_uncheck( m_grp, m_alongsideButton ); // Husk erase-only\n'
        '    force_uncheck( m_grp, m_replaceButton );\n'
        '    force_uncheck( m_grp, m_somethingElseButton );\n\n'
        '    if ( m_somethingElseButton->isHidden() && m_alongsideButton->isHidden() && m_replaceButton->isHidden()\n')
    # Complete all validations before mutating the extracted build tree.
    header = (assets / 'HuskDiskGuard.h').read_text()
    umount_path = source/'src/modules/umount/UmountJob.cpp'
    umount = umount_path.read_text()
    umount = replace(umount, 'Calamares::Partition::unmount( m.mountPoint, { "-lv" } )',
                     'Calamares::Partition::unmount( m.mountPoint, { "-v" } )')
    umount = replace(umount, 'Calamares::Partition::unmount( rootMountPoint, { "-lv" } )',
                     'Calamares::Partition::unmount( rootMountPoint, { "-v" } )')
    for n, value in [('core/DeviceList.cpp',devices),('core/PartitionCoreModule.cpp',jobs),('gui/ChoicePage.cpp',choices)]:
        paths[n].write_text(value)
    (base / 'HuskDiskGuard.h').write_text(header)
    umount_path.write_text(umount)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    apply(args.source, args.assets)
