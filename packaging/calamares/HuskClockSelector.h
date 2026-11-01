// SPDX-License-Identifier: GPL-3.0-or-later
// Geographic time-zone selection for the pinned Calamares locale module.
#ifndef HUSK_CLOCK_SELECTOR_H
#define HUSK_CLOCK_SELECTOR_H

#include <QButtonGroup>
#include <QComboBox>
#include <QDateTime>
#include <QFile>
#include <QGridLayout>
#include <QLabel>
#include <QMap>
#include <QPushButton>
#include <QRegularExpression>
#include <QScrollArea>
#include <QSet>
#include <QSignalBlocker>
#include <QTimeZone>
#include <QTimer>
#include <QVBoxLayout>
#include <QWidget>

#include <algorithm>
#include <cstdlib>
#include <functional>

class HuskClockSelector : public QWidget
{
public:
    // Empty zone + false invalidates a previous choice when another clock is clicked.
    std::function< void( const QString& zone, bool valid ) > selectedZone;

    explicit HuskClockSelector( QWidget* parent = nullptr,
                                const QString& zoneTab = QStringLiteral( "/usr/share/zoneinfo/zone.tab" ) )
        : QWidget( parent )
        , m_regions( readRegions( zoneTab ) )
    {
        auto* layout = new QVBoxLayout( this );
        auto* instructions = new QLabel(
            QStringLiteral( "Choose a clock, then select your region or city. "
                            "Regional time zones adjust automatically for daylight saving time." ), this );
        instructions->setWordWrap( true );
        layout->addWidget( instructions );

        auto* scroll = new QScrollArea( this );
        scroll->setWidgetResizable( true );
        scroll->setFrameShape( QFrame::NoFrame );
        auto* gridWidget = new QWidget( scroll );
        m_grid = new QGridLayout( gridWidget );
        m_grid->setContentsMargins( 0, 0, 0, 0 );
        m_grid->setSpacing( 6 );
        scroll->setWidget( gridWidget );
        layout->addWidget( scroll, 1 );
        m_group = new QButtonGroup( this );
        m_group->setExclusive( true );

        auto* regionLabel = new QLabel( QStringLiteral( "Region / city:" ), this );
        m_regionCombo = new QComboBox( this );
        m_regionCombo->setObjectName( QStringLiteral( "husk-region" ) );
        m_regionCombo->setAccessibleName( QStringLiteral( "Region or city" ) );
        m_regionCombo->setSizePolicy( QSizePolicy::Expanding, QSizePolicy::Preferred );
        regionLabel->setBuddy( m_regionCombo );
        layout->addWidget( regionLabel );
        layout->addWidget( m_regionCombo );
        m_hint = new QLabel( this );
        m_hint->setWordWrap( true );
        m_hint->setMinimumHeight( 36 );
        layout->addWidget( m_hint );
        connect( m_regionCombo, QOverload< int >::of( &QComboBox::currentIndexChanged ), this, [ this ]( int ) {
            m_selectedId = m_regionCombo->currentData().toString();
            notifySelection();
        } );

        refreshClocks( QDateTime::currentDateTimeUtc() );
        auto* timer = new QTimer( this );
        timer->setObjectName( QStringLiteral( "husk-clock-timer" ) );
        timer->setInterval( 1000 );
        connect( timer, &QTimer::timeout, this, [ this ] { refreshClocks( QDateTime::currentDateTimeUtc() ); } );
        timer->start();
    }

    QString selectedIanaZone() const { return selectionValid() ? m_selectedId : QString(); }

    bool selectionValid() const
    {
        return !m_selectedId.isEmpty() && m_regionCombo->currentData().toString() == m_selectedId
            && m_groups.value( m_selectedOffset ).contains( m_selectedId );
    }

    void focusRegion() { m_regionCombo->setFocus(); }

    // QTimeZone, rather than a stored UTC offset, determines each region's group.
    // Retain the IANA choice when a DST transition changes its current offset.
    void refreshClocks( const QDateTime& instant )
    {
        if ( !instant.isValid() )
        {
            return;
        }
        m_now = instant.toUTC();
        QMap< int, QStringList > groups;
        QSet< int > offsets;
        for ( int hour = -12; hour <= 14; ++hour )
        {
            offsets.insert( hour * 3600 );
        }
        for ( const auto& region : m_regions )
        {
            const int offset = region.zone.offsetFromUtc( m_now );
            groups[ offset ].append( region.id );
            offsets.insert( offset );  // Include actual half-hour and quarter-hour regions.
            if ( region.id == m_selectedId )
            {
                m_selectedOffset = offset;
            }
        }
        auto ordered = offsets.values();
        std::sort( ordered.begin(), ordered.end() );
        if ( ordered != m_offsets )
        {
            m_offsets = ordered;
            rebuildClocks();
        }
        if ( groups != m_groups || m_regionCombo->count() == 0 )
        {
            m_groups = groups;
            fillRegions();
        }
        for ( auto it = m_buttons.cbegin(); it != m_buttons.cend(); ++it )
        {
            it.value()->setText( offsetLabel( it.key() ) + '\n' + m_now.addSecs( it.key() ).toString( "HH:mm" ) );
            it.value()->setChecked( it.key() == m_selectedOffset );
        }
        notifySelection();
    }

private:
    struct Region
    {
        QString id;
        QTimeZone zone;
    };

    static QList< Region > readRegions( const QString& path )
    {
        QList< Region > regions;
        QFile file( path );
        if ( !file.open( QIODevice::ReadOnly | QIODevice::Text ) )
        {
            return regions;
        }
        QSet< QString > seen;
        const QRegularExpression country( QStringLiteral( "^[A-Z]{2}(,[A-Z]{2})*$" ) );
        const QRegularExpression name( QStringLiteral( "^[A-Za-z_+-]+(/[A-Za-z0-9_+-]+)+$" ) );
        while ( !file.atEnd() )
        {
            const auto line = QString::fromUtf8( file.readLine() ).trimmed();
            if ( line.isEmpty() || line.startsWith( '#' ) )
            {
                continue;
            }
            const auto fields = line.split( QRegularExpression( QStringLiteral( "\\s+" ) ), Qt::SkipEmptyParts );
            if ( fields.size() < 3 || !country.match( fields[ 0 ] ).hasMatch() )
            {
                continue;
            }
            const QString id = fields[ 2 ];
            const QTimeZone zone( id.toUtf8() );
            if ( !name.match( id ).hasMatch() || id.startsWith( "Etc/" ) || !zone.isValid() || seen.contains( id ) )
            {
                continue;
            }
            seen.insert( id );
            regions.append( { id, zone } );
        }
        std::sort( regions.begin(), regions.end(), []( const Region& a, const Region& b ) { return a.id < b.id; } );
        return regions;
    }

    static QString offsetLabel( int seconds )
    {
        const int minutes = std::abs( seconds ) / 60;
        return QStringLiteral( "UTC%1%2:%3" )
            .arg( seconds < 0 ? '-' : '+' )
            .arg( minutes / 60, 2, 10, QChar( '0' ) )
            .arg( minutes % 60, 2, 10, QChar( '0' ) );
    }

    void rebuildClocks()
    {
        while ( auto* item = m_grid->takeAt( 0 ) )
        {
            delete item->widget();
            delete item;
        }
        m_buttons.clear();
        int position = 0;
        for ( const int offset : m_offsets )
        {
            auto* button = new QPushButton( this );
            button->setObjectName( QStringLiteral( "husk-offset-%1" ).arg( offset ) );
            button->setAccessibleName( offsetLabel( offset ) );
            button->setCheckable( true );
            button->setMinimumSize( 84, 58 );
            button->setToolTip( QStringLiteral( "Choose %1, then a geographic region." ).arg( offsetLabel( offset ) ) );
            m_group->addButton( button );
            m_buttons.insert( offset, button );
            m_grid->addWidget( button, position / 7, position % 7 );
            ++position;
            connect( button, &QPushButton::clicked, this, [ this, offset ] {
                m_selectedOffset = offset;
                m_selectedId.clear();
                fillRegions();
                notifySelection();
            } );
        }
        m_grid->setRowStretch( ( position + 6 ) / 7, 1 );
    }

    void fillRegions()
    {
        const QSignalBlocker blocker( m_regionCombo );
        m_regionCombo->clear();
        m_regionCombo->addItem( QStringLiteral( "Choose a region / city" ), QString() );
        const auto ids = m_groups.value( m_selectedOffset );
        for ( const auto& id : ids )
        {
            QString label = id;
            label.replace( '_', ' ' );
            m_regionCombo->addItem( label, id );
        }
        int index = m_regionCombo->findData( m_selectedId );
        m_regionCombo->setCurrentIndex( index > 0 ? index : 0 );
        if ( index <= 0 )
        {
            m_selectedId.clear();
        }
        m_regionCombo->setEnabled( !ids.isEmpty() );
        m_hint->setText( m_regions.isEmpty()
                ? QStringLiteral( "The geographic time zone database is unavailable. Installation cannot continue." )
                : ids.isEmpty()
                ? QStringLiteral( "No geographic region currently uses %1. Choose another clock to continue." )
                      .arg( offsetLabel( m_selectedOffset ) )
                : QStringLiteral( "Select a named region to continue. Your selected region keeps its daylight saving rules." ) );
    }

    void notifySelection()
    {
        const QString id = selectedIanaZone();
        const bool valid = selectionValid();
        if ( id == m_lastId && valid == m_lastValid )
        {
            return;
        }
        m_lastId = id;
        m_lastValid = valid;
        if ( selectedZone )
        {
            selectedZone( id, valid );
        }
    }

    QList< Region > m_regions;
    QDateTime m_now;
    QList< int > m_offsets;
    QMap< int, QStringList > m_groups;
    QMap< int, QPushButton* > m_buttons;
    QGridLayout* m_grid = nullptr;
    QButtonGroup* m_group = nullptr;
    QComboBox* m_regionCombo = nullptr;
    QLabel* m_hint = nullptr;
    int m_selectedOffset = 0;
    QString m_selectedId;
    QString m_lastId;
    bool m_lastValid = false;
};

#endif  // HUSK_CLOCK_SELECTOR_H
