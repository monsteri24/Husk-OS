"""Pinned-source patch checks and real Qt (offscreen) behavior tests.

Set CALAMARES_SOURCE_DIR to an unmodified 3.3.14 tree for patch tests.
Qt tests require Qt6 Widgets, Qml, Quick development files and QML modules.
Offscreen Qt checks do not establish ISO, compositor or installer acceptance.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/patch-calamares-ui.py'
ASSETS = ROOT / 'packaging/calamares'
UPSTREAM = Path(os.environ.get('CALAMARES_SOURCE_DIR', ROOT.parent / 'calamares-3.3.14'))
PATCHED_FILES = (
    'src/modules/locale/LocalePage.cpp',
    'src/modules/locale/LocalePage.h',
    'src/modules/locale/LocaleViewStep.cpp',
    'src/modules/finishedq/FinishedQmlViewStep.cpp',
    'src/modules/finishedq/finishedq.qml',
    'src/modules/finishedq/finishedq-qt6.qml',
    'src/modules/welcome/WelcomePage.cpp',
)


class CalamaresUiPatchTests(unittest.TestCase):
    def test_ui_patch_and_assets_exist(self):
        for path in (SCRIPT, ASSETS / 'HuskClockSelector.h', ASSETS / 'husk-finished.qml'):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f'Missing Calamares UI implementation: {path}')

    def fixture(self, directory):
        if not all((UPSTREAM / name).is_file() for name in PATCHED_FILES):
            self.skipTest('Unmodified Calamares 3.3.14 source fixture unavailable')
        for name in PATCHED_FILES + ('src/modules/locale/Config.cpp',):
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(UPSTREAM / name, target)

    def patch(self, source):
        self.assertTrue(SCRIPT.is_file(), 'Calamares exact-source UI patch is missing')
        return subprocess.run([sys.executable, str(SCRIPT), str(source), '--assets', str(ASSETS)],
                              capture_output=True, text=True)

    @staticmethod
    def snapshot(source):
        return {str(path.relative_to(source)): path.read_bytes()
                for path in source.rglob('*') if path.is_file()}

    def test_patch_keeps_config_and_connects_real_iana_selection_to_next(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            self.fixture(source)
            config = (source / 'src/modules/locale/Config.cpp').read_bytes()
            result = self.patch(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            page = (source / PATCHED_FILES[0]).read_text()
            step = (source / PATCHED_FILES[2]).read_text()
            self.assertNotIn('new TimeZoneWidget', page)
            self.assertIn('m_config->zonesModel()->find', page)
            self.assertIn('m_config->setCurrentLocation( location )', page)
            self.assertIn('setLanguageExplicitly( QStringLiteral( "en_US.UTF-8" ) )', page)
            self.assertIn('setLCLocaleExplicitly( QStringLiteral( "en_US.UTF-8" ) )', page)
            self.assertIn('&LocalePage::huskSelectionValid', step)
            self.assertIn('m_nextEnabled = m_actualWidget->huskHasSelection()', step)
            self.assertNotIn('m_nextEnabled = true;', step)
            self.assertEqual((source / 'src/modules/locale/Config.cpp').read_bytes(), config)
            self.assertEqual((source / 'src/modules/locale/HuskClockSelector.h').read_bytes(),
                             (ASSETS / 'HuskClockSelector.h').read_bytes())
            for name in PATCHED_FILES[4:6]:
                self.assertEqual((source / name).read_bytes(), (ASSETS / 'husk-finished.qml').read_bytes())
            finished = (source / PATCHED_FILES[3]).read_text()
            self.assertNotIn('&QApplication::aboutToQuit', finished)
            welcome = (source / PATCHED_FILES[6]).read_text()
            self.assertIn('ui->languageWidget->setEnabled( false );', welcome)

    def test_source_drift_fails_before_any_file_is_changed(self):
        for changed in PATCHED_FILES:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as temporary:
                source = Path(temporary)
                self.fixture(source)
                with (source / changed).open('ab') as stream:
                    stream.write(b'\n// source drift\n')
                before = self.snapshot(source)
                result = self.patch(source)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('source mismatch', result.stderr.lower())
                self.assertEqual(self.snapshot(source), before)

    def test_second_application_and_symlink_escape_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            self.fixture(source)
            self.assertEqual(self.patch(source).returncode, 0)
            before = self.snapshot(source)
            self.assertNotEqual(self.patch(source).returncode, 0)
            self.assertEqual(self.snapshot(source), before)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            self.fixture(source)
            path = source / PATCHED_FILES[-1]
            outside = Path(temporary) / 'outside.cpp'
            path.replace(outside)
            path.symlink_to(outside)
            before = outside.read_bytes()
            result = self.patch(source)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(outside.read_bytes(), before)
            self.assertFalse((source / 'src/modules/locale/HuskClockSelector.h').exists())

    def test_replacing_a_hard_link_does_not_change_an_outside_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            self.fixture(source)
            outside = Path(temporary) / 'outside.cpp'
            path = source / PATCHED_FILES[0]
            os.link(path, outside)
            before = outside.read_bytes()
            result = self.patch(source)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(outside.read_bytes(), before, 'Patch must replace its own entry without writing through hard links')


QT_BEHAVIOR = r'''
#include "HuskClockSelector.h"
#include <QApplication>
#include <QFile>
#include <QJsonArray>
#include <QMetaObject>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QTextStream>
#include <QVariant>
#include <memory>

static void check(bool condition, const char* message)
{
    if (!condition) { qFatal("%s", message); }
}

int main(int argc, char** argv)
{
    QApplication application(argc, argv);
    const QString fixture = QString::fromLocal8Bit(argv[1]);
    const QDateTime winter = QDateTime::fromString("2026-01-15T10:00:00Z", Qt::ISODate);
    const QDateTime summer = QDateTime::fromString("2026-07-15T10:00:00Z", Qt::ISODate);
    HuskClockSelector clocks(nullptr, fixture);
    clocks.refreshClocks(winter);
    auto* regions = clocks.findChild<QComboBox*>("husk-region");
    check(regions && !clocks.selectionValid(), "a region must be chosen explicitly");
    for (int hour = -12; hour <= 14; ++hour)
    {
        auto* button = clocks.findChild<QPushButton*>(QString("husk-offset-%1").arg(hour * 3600));
        check(button, "every whole UTC hour needs a clock");
        check(button->text().contains(winter.addSecs(hour * 3600).toString("HH:mm")), "clock must show actual time");
    }
    QString chosen;
    bool valid = false;
    clocks.selectedZone = [&](const QString& zone, bool ok) { chosen = zone; valid = ok; };
    auto chooseOffset = [&](int seconds) {
        auto* button = clocks.findChild<QPushButton*>(QString("husk-offset-%1").arg(seconds));
        check(button, "required fractional clock is absent");
        button->click();
    };
    chooseOffset(2 * 3600);
    check(regions->findData("Europe/Helsinki") > 0, "winter Helsinki must use UTC+02:00");
    check(regions->findData("Asia/Kathmandu") < 0, "offset must narrow region choices");
    regions->setCurrentIndex(regions->findData("Europe/Helsinki"));
    check(valid && chosen == "Europe/Helsinki" && clocks.selectionValid(), "chosen IANA region must reach callback");
    clocks.refreshClocks(summer);
    check(clocks.selectionValid() && clocks.selectedIanaZone() == "Europe/Helsinki", "DST must retain chosen IANA region");
    check(clocks.findChild<QPushButton*>("husk-offset-10800")->isChecked(), "DST must follow actual zone offset");
    chooseOffset(5 * 3600 + 45 * 60);
    check(!valid && chosen.isEmpty(), "changing offset must clear prior region validity");
    check(regions->findData("Asia/Kathmandu") > 0, "fractional IANA zone must be selectable");
    regions->setCurrentIndex(regions->findData("Asia/Kathmandu"));
    check(clocks.selectionValid() && chosen == "Asia/Kathmandu", "fractional zone must retain named region");
    chooseOffset(-12 * 3600);
    check(!clocks.selectionValid() && !valid && regions->count() == 1, "UTC-12 cannot silently become a fixed zone");
    check(regions->findData("Etc/GMT+12") < 0, "fixed-offset aliases are not geographic regions");
    clocks.refreshClocks(winter.addSecs(60));
    check(clocks.findChild<QPushButton*>("husk-offset--43200")->text().contains("22:01"), "clock refresh must tick");
    HuskClockSelector missing(nullptr, fixture + ".missing");
    check(!missing.selectionValid(), "missing zone.tab must fail closed");

    QQmlEngine engine;
    engine.addImportPath(QString::fromLocal8Bit(argv[2]));
    QQmlComponent mock(&engine);
    mock.setData(R"QML(import QtQml
QtObject {
    property bool failed: false
    property bool restartNowWanted: true
    property string failureMessage: "Disk write failed"
    property string failureDetails: "Test failure details"
    property int restarts: 0
    signal failureChanged(bool failed)
    onFailedChanged: failureChanged(failed)
    function doRestart(force) { if (force) restarts += 1 }
})QML", QUrl());
    std::unique_ptr<QObject> config(mock.create());
    check(bool(config), qPrintable(mock.errorString()));
    engine.rootContext()->setContextProperty("config", config.get());
    QQmlComponent page(&engine, QUrl::fromLocalFile(QString::fromLocal8Bit(argv[3])));
    auto create = [&]() {
        auto object = std::unique_ptr<QObject>(page.create());
        check(bool(object), qPrintable(page.errorString()));
        return object;
    };
    auto invoke = [](QObject* object, const char* method) {
        check(QMetaObject::invokeMethod(object, method), "QML action invocation failed");
    };
    auto hasText = [](QObject* object, const QString& text) {
        for (const auto* child : object->findChildren<QObject*>())
        {
            if (child->property("text").toString() == text) { return true; }
        }
        return false;
    };
    auto object = create();
    auto timer = object->findChild<QObject*>("husk-restart-timer");
    check(timer && !timer->property("running").toBool(), "countdown cannot run when QML is constructed");
    invoke(object.get(), "onActivate");
    check(timer->property("running").toBool() && object->property("secondsRemaining").toInt() == 30, "success activation must begin at 30");
    check(object->findChild<QObject*>("husk-finish-title")->property("text").toString() == "Installation Complete", "success title must be exact");
    check(hasText(object.get(), "Restarting in 30 seconds..."), "countdown must begin with exact text and ellipsis");
    check(!config->property("restartNowWanted").toBool(), "auto restart wanted must remain false");
    invoke(timer, "triggered");
    check(hasText(object.get(), "Restarting in 29 seconds..."), "countdown text must decrease with each tick");
    for (int tick = 1; tick < 29; ++tick) { invoke(timer, "triggered"); }
    check(config->property("restarts").toInt() == 0 && object->property("secondsRemaining").toInt() == 1, "restart cannot happen early");
    check(hasText(object.get(), "Restarting in 1 seconds..."), "countdown text must show remaining seconds");
    invoke(timer, "triggered");
    check(config->property("restarts").toInt() == 1 && object->property("secondsRemaining").toInt() == 0, "30th tick must restart once");
    check(hasText(object.get(), "Restarting in 0 seconds..."), "countdown text must reach zero");
    invoke(timer, "triggered");
    check(config->property("restarts").toInt() == 1, "restart must be idempotent");
    object.reset();
    object = create();
    timer = object->findChild<QObject*>("husk-restart-timer");
    invoke(object.get(), "onActivate");
    invoke(object.get(), "restartLater");
    invoke(timer, "triggered");
    check(!timer->property("running").toBool() && config->property("restarts").toInt() == 1, "Later must stop countdown and suppress restart");
    // The fixture is a URL-based QML singleton, not a C++ registered qmlTypeId.
    QQmlComponent managerProbe(&engine);
    managerProbe.setData("import QtQml\nimport io.calamares.core 1.0\n"
                         "QtObject { property QtObject manager: ViewManager }", QUrl());
    std::unique_ptr<QObject> probe(managerProbe.create());
    check(bool(probe), qPrintable(managerProbe.errorString()));
    auto* manager = probe->property("manager").value<QObject*>();
    check(manager && manager->property("quits").toInt() == 1, "Later must quit installer");
    object.reset();
    object = create();
    timer = object->findChild<QObject*>("husk-restart-timer");
    config->setProperty("failed", true);
    invoke(object.get(), "onActivate");
    invoke(timer, "triggered");
    invoke(object.get(), "restartNow");
    check(!timer->property("running").toBool() && config->property("restarts").toInt() == 1, "failed installs must never start or request restart");
    check(object->findChild<QObject*>("husk-finish-title")->property("text").toString() == "Installation Failed", "failure must not show success title");
    config->setProperty("failed", false);
    invoke(object.get(), "onActivate");
    config->setProperty("failed", true);
    check(!timer->property("running").toBool(), "late failure must stop active timer");
    object.reset();
    config->setProperty("failed", false);
    object = create();
    invoke(object.get(), "onActivate");
    invoke(object.get(), "restartNow");
    check(config->property("restarts").toInt() == 2, "Now must request immediate restart");
    invoke(object.get(), "onLeave");
    check(!object->findChild<QObject*>("husk-restart-timer")->property("running").toBool(), "leaving must stop timer");
    auto* later = object->findChild<QQuickItem*>("husk-restart-later");
    auto* now = object->findChild<QQuickItem*>("husk-restart-now");
    check(later && now && later->property("text") == "Restart Later" && now->property("text") == "Restart Now", "button labels must be exact");
    QCoreApplication::processEvents();
    check(later->x() < now->x(), "Later must be left of Now");
    QTextStream(stdout) << "Qt clock and completion behavior passed\n";
}
'''


class CalamaresQtUiTests(unittest.TestCase):
    def test_real_qt_clock_and_completion_behaviour(self):
        self.assertTrue((ASSETS / 'HuskClockSelector.h').is_file(), 'Clock selector is missing')
        self.assertTrue((ASSETS / 'husk-finished.qml').is_file(), 'Completion QML is missing')
        if not shutil.which('pkg-config') or not shutil.which('c++'):
            self.skipTest('Qt6 development toolchain unavailable')
        flags = subprocess.run(['pkg-config', '--cflags', '--libs', 'Qt6Widgets', 'Qt6Qml', 'Qt6Quick'],
                               capture_output=True, text=True)
        if flags.returncode:
            self.skipTest('Qt6 Widgets/Qml/Quick development packages unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            cpp = directory / 'calamares-ui.cpp'
            cpp.write_text(QT_BEHAVIOR)
            binary = directory / 'calamares-ui'
            compile_result = subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                  '-fPIC', '-I', str(ASSETS), str(cpp), '-o', str(binary), *shlex.split(flags.stdout)],
                  capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            zones = directory / 'zone.tab'
            zones.write_text('# test IANA geographic zones\nFI\t+6010+02458\tEurope/Helsinki\n'
                             'NP\t+2743+08519\tAsia/Kathmandu\nNZ\t-4357-17633\tPacific/Chatham\n'
                             'KI\t+0152-15720\tPacific/Kiritimati\nXX\t+0000+00000\tEtc/GMT+12\n')
            module = directory / 'imports/io/calamares/core'
            module.mkdir(parents=True)
            (module / 'qmldir').write_text('module io.calamares.core\nsingleton ViewManager 1.0 ViewManager.qml\n')
            (module / 'ViewManager.qml').write_text('pragma Singleton\nimport QtQml\n'
                  'QtObject { property int quits: 0; function quit() { quits += 1 } }\n')
            environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
            if environment.get('HUSK_TEST_SYSROOT'):
                prefix = Path(environment['HUSK_TEST_SYSROOT']) / 'usr/lib/x86_64-linux-gnu/qt6'
                environment['QT_PLUGIN_PATH'] = str(prefix / 'plugins')
                environment['QML_IMPORT_PATH'] = str(prefix / 'qml')
                environment['QML2_IMPORT_PATH'] = str(prefix / 'qml')
            result = subprocess.run([str(binary), str(zones), str(directory / 'imports'),
                                     str(ASSETS / 'husk-finished.qml')],
                                    capture_output=True, text=True, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Qt clock and completion behavior passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
