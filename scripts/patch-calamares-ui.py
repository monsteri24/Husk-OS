#!/usr/bin/env python3
"""Apply Husk's UI to exactly the reviewed Calamares 3.3.14 source files.

Usage: patch-calamares-ui.py CALAMARES_SOURCE [--assets DIRECTORY]
DIRECTORY contains HuskClockSelector.h and husk-finished.qml. All source
hashes, literal replacement counts and destinations are checked before writes.
The locale Config and installation jobs remain upstream implementations.
"""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile


# Files from the release tarball pinned in packaging/calamares/PKGBUILD.
SOURCE_SHA256 = {
    'src/modules/locale/LocalePage.cpp': 'fd0a8a41773caeb631bbbcfe5377ae325960497b6b5cd9372823c8521eecc391',
    'src/modules/locale/LocalePage.h': '5bf7b5a81669179c6f993144defb43e0903d621dd67d8676dbcfeb961b52eb2b',
    'src/modules/locale/LocaleViewStep.cpp': '0313e6a852551457a2ee744db4a315bb442869b55246593c6a21dcd3a71dbf01',
    'src/modules/finishedq/FinishedQmlViewStep.cpp': '75ee6f2fcc46d03589244490b45abfbc5a69585660fd22fe3d420f2ebdf22082',
    'src/modules/finishedq/finishedq.qml': '05fc9f3e122bd0b73aeb9cfa920ab1d2328f8817f6368400004c390cc407f7d0',
    'src/modules/finishedq/finishedq-qt6.qml': '4b037519e5276a0cdd5a565834c7922abedf8ca736cde8b040f11c315c88fabb',
    'src/modules/welcome/WelcomePage.cpp': '092bf5d74b4c910cd8112761bac17daf875b05477ad5a8b83538718b73508a5d',
    'src/modules/partition/gui/PartitionLabelsView.cpp': '0a19b5be9a2c74eabf0f5190bb4b87410f7a379e59b6e8e37ee1baa144cfb87b',
}

LOCALE_PAGE = '''#include "LocalePage.h"

#include "Config.h"
#include "HuskClockSelector.h"

#include <QLabel>
#include <QVBoxLayout>

LocalePage::LocalePage( Config* config, QWidget* parent )
    : QWidget( parent )
    , m_config( config )
    , m_clocks( new HuskClockSelector( this ) )
{
    // English is the installed locale as well as the fixed installer UI.
    m_config->setLanguageExplicitly( QStringLiteral( "en_US.UTF-8" ) );
    m_config->setLCLocaleExplicitly( QStringLiteral( "en_US.UTF-8" ) );
    auto* layout = new QVBoxLayout( this );
    layout->addWidget( m_clocks, 1 );
    auto* language = new QLabel( QStringLiteral( "Language: English (United States)" ), this );
    auto* formats = new QLabel( QStringLiteral( "Formats: English (United States)" ), this );
    layout->addWidget( language );
    layout->addWidget( formats );

    m_clocks->selectedZone = [ this ]( const QString& id, bool valid ) {
        if ( valid )
        {
            const int slash = id.indexOf( '/' );
            const auto* location = slash > 0
                ? m_config->zonesModel()->find( id.left( slash ), id.mid( slash + 1 ) ) : nullptr;
            valid = location && id == location->region() + '/' + location->zone();
            if ( valid )
            {
                // Preserve upstream IANA selection, summary, jobs and finalization.
                m_config->setCurrentLocation( location );
            }
        }
        emit huskSelectionValid( valid );
    };
}

LocalePage::~LocalePage() {}

bool
LocalePage::huskHasSelection() const
{
    const auto* location = m_config->currentLocation();
    return m_clocks->selectionValid() && location
        && m_clocks->selectedIanaZone() == location->region() + '/' + location->zone();
}

void
LocalePage::onActivate()
{
    m_clocks->refreshClocks( QDateTime::currentDateTimeUtc() );
    m_clocks->focusRegion();
    emit huskSelectionValid( huskHasSelection() );
}
'''

LOCALE_HEADER = '''#ifndef LOCALEPAGE_H
#define LOCALEPAGE_H

#include <QWidget>

class Config;
class HuskClockSelector;

class LocalePage : public QWidget
{
    Q_OBJECT
public:
    explicit LocalePage( Config* config, QWidget* parent = nullptr );
    ~LocalePage() override;
    void onActivate();
    bool huskHasSelection() const;

signals:
    void huskSelectionValid( bool valid );

private:
    Config* m_config;
    HuskClockSelector* m_clocks;
};

#endif  // LOCALEPAGE_H
'''


def safe_path(root, relative):
    path = root
    for component in Path(relative).parts:
        if component in ('.', '..'):
            raise ValueError(f'Invalid patch destination: {relative}')
        path /= component
        if path.is_symlink():
            raise ValueError(f'Symlink patch destination refused: {relative}')
    return path


def replace_once(text, old, new, name):
    if text.count(old) != 1:
        raise ValueError(f'Exact replacement mismatch: {name}')
    return text.replace(old, new, 1)


def with_original_notice(text, marker, replacement, name):
    if text.count(marker) != 1:
        raise ValueError(f'Original source notice mismatch: {name}')
    return text.split(marker, 1)[0] + replacement


def patch(source, assets):
    root = source.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Calamares source must be a directory')
    originals = {}
    for name, expected in SOURCE_SHA256.items():
        path = safe_path(root, name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Calamares 3.3.14 source mismatch: {name}')
        originals[name] = data.decode('utf-8')

    header_name = 'src/modules/locale/HuskClockSelector.h'
    header = safe_path(root, header_name)
    if header.exists():
        raise ValueError(f'New patch destination already exists: {header_name}')
    asset_data = {}
    for name in ('HuskClockSelector.h', 'husk-finished.qml'):
        path = assets / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing regular UI asset: {path}')
        asset_data[name] = path.read_text(encoding='utf-8')
        if not asset_data[name].strip():
            raise ValueError(f'Empty UI asset: {path}')

    changes = {}
    page_name = 'src/modules/locale/LocalePage.cpp'
    changes[page_name] = with_original_notice(originals[page_name], '#include "LocalePage.h"',
                                             LOCALE_PAGE, page_name)
    page_header = 'src/modules/locale/LocalePage.h'
    changes[page_header] = with_original_notice(originals[page_header], '#ifndef LOCALEPAGE_H',
                                               LOCALE_HEADER, page_header)
    step = 'src/modules/locale/LocaleViewStep.cpp'
    changes[step] = replace_once(originals[step],
        '        m_actualWidget = new LocalePage( m_config.get() );\n',
        '''        m_actualWidget = new LocalePage( m_config.get() );
        connect( m_actualWidget, &LocalePage::huskSelectionValid, this, [ this ]( bool valid ) {
            m_nextEnabled = valid;
            emit nextStatusChanged( m_nextEnabled );
        } );
''', step)
    changes[step] = replace_once(changes[step], '    m_nextEnabled = true;\n',
                                '    m_nextEnabled = m_actualWidget->huskHasSelection();\n', step)
    finish = 'src/modules/finishedq/FinishedQmlViewStep.cpp'
    changes[finish] = replace_once(originals[finish],
        '    connect( qApp, &QApplication::aboutToQuit, m_config, qOverload<>( &Config::doRestart ) );\n',
        '    // Husk QML requests restart explicitly; closing the installer never restarts.\n', finish)
    welcome = 'src/modules/welcome/WelcomePage.cpp'
    changes[welcome] = replace_once(originals[welcome],
        '    ui->languageWidget->setCurrentIndex( m_conf->localeIndex() );\n',
        '''    ui->languageWidget->setCurrentIndex( m_conf->localeIndex() );
    // The Live launcher sets en_US.UTF-8; language changes are postponed.
    ui->languageWidget->setEnabled( false );
''', welcome)
    legend = 'src/modules/partition/gui/PartitionLabelsView.cpp'
    if originals[legend].count('painter->setPen( Qt::black );') != 2:
        raise ValueError('Exact replacement mismatch: partition legend text')
    changes[legend] = originals[legend].replace('painter->setPen( Qt::black );',
        'painter->setPen( palette().color( QPalette::WindowText ) );')
    changes[legend] = replace_once(changes[legend], 'painter->setPen( Qt::gray );',
        'painter->setPen( palette().color( QPalette::WindowText ) );', legend)
    for name in ('src/modules/finishedq/finishedq.qml', 'src/modules/finishedq/finishedq-qt6.qml'):
        changes[name] = asset_data['husk-finished.qml']
    changes[header_name] = asset_data['HuskClockSelector.h']

    # Stage all data before replacing entries. Replacement also avoids writing
    # through a hard link into a different source tree or an outside backup.
    # No source/asset validation or replacement is deferred until after writes.
    staged = []
    try:
        for name, text in changes.items():
            destination = safe_path(root, name)
            fd, filename = tempfile.mkstemp(prefix='.husk-ui-', dir=destination.parent)
            temporary = Path(filename)
            staged.append((temporary, destination))
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                stream.write(text)
            mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
            temporary.chmod(mode)
        for temporary, destination in staged:
            temporary.replace(destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='unmodified Calamares 3.3.14 source directory')
    parser.add_argument('--assets', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'packaging/calamares')
    args = parser.parse_args()
    try:
        patch(args.source, args.assets)
    except (OSError, ValueError) as error:
        print(f'Husk Calamares UI patch refused: {error}', file=sys.stderr)
        return 1
    print('Applied Husk clocks and completion UI to verified Calamares 3.3.14 source files.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
