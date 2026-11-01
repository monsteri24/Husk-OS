// SPDX-License-Identifier: MIT
// Read-only identity checks around Calamares's existing KPMCore jobs.
#pragma once
#include "Job.h"
#include <QMap>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QRegularExpression>

namespace HuskDiskGuard {
inline QMap<QString, QByteArray>& snapshots() { static QMap<QString, QByteArray> values; return values; }
inline QByteArray run(const QStringList& args) {
    QProcess p;
    p.start(QStringLiteral("/usr/lib/ownos/husk-install-guard"), args);
    if (!p.waitForStarted(3000)) return {};
    if (!p.waitForFinished(30000)) { p.kill(); p.waitForFinished(); return {}; }
    const QByteArray out = p.readAllStandardOutput().trimmed();
    if (p.exitStatus() != QProcess::NormalExit || p.exitCode() != 0) return {};
    return out;
}
inline QByteArray query(const QStringList& args) {
    const auto out = run(args);
    return QRegularExpression(QStringLiteral("^[0-9a-f]{64}$")).match(QString::fromLatin1(out)).hasMatch() ? out : QByteArray();
}
inline void beginScan() {
    // Capture identities BEFORE KPM scans; verify AFTER its scan. Never
    // overwrite this snapshot with a same-name replacement observed later.
    snapshots().clear();
    const auto doc = QJsonDocument::fromJson(run({QStringLiteral("inventory")}));
    if (!doc.isObject()) return;
    const auto object = doc.object();
    for (auto i=object.begin(); i!=object.end(); ++i) {
        const auto value = i.value().toString().toLatin1();
        if (QRegularExpression(QStringLiteral("^[0-9a-f]{64}$")).match(QString::fromLatin1(value)).hasMatch())
            snapshots().insert(i.key(), value);
    }
}
inline bool capture(const QString& device) {
    const auto expected = snapshots().value(device);
    return !expected.isEmpty() && query({QStringLiteral("verify"),device,QString::fromLatin1(expected)}) == expected;
}
}

class HuskDiskGuardJob : public Calamares::Job {
    QString m_device;
    QByteArray m_expected;
public:
    explicit HuskDiskGuardJob(const QString& device)
      : m_device(device), m_expected(HuskDiskGuard::snapshots().value(device)) {}
    QString prettyName() const override { return QStringLiteral("Verify installation drive and protect Live USB"); }
    Calamares::JobResult exec() override {
        if (m_expected.isEmpty() || HuskDiskGuard::query({QStringLiteral("verify"),m_device,
            QString::fromLatin1(m_expected)}) != m_expected)
            return Calamares::JobResult::error(QStringLiteral("Installation drive safety check failed"),
                QStringLiteral("The drive changed, is mounted, or is the Live installation medium. No partitioning was started. Return to drive selection."));
        return Calamares::JobResult::ok();
    }
};
