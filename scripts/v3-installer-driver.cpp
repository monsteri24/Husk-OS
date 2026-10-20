// Test fixture only. Never installed into the ISO or linked into Calamares.
// Build with c++ -std=c++17 -fPIC -shared and pkg-config flags from
// Qt6Widgets Qt6Test Qt6Quick. The output is a separate test-only driver.so.
// All installation decisions use actual Qt mouse/key events. No Calamares
// storage, jobs, view-manager methods or completion functions are invoked here.
#include <QApplication>
#include <QAbstractItemView>
#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListView>
#include <QMessageBox>
#include <QPointer>
#include <QPushButton>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRadioButton>
#include <QScrollArea>
#include <QSet>
#include <QStandardPaths>
#include <QStackedWidget>
#include <QTest>
#include <QTimer>
#include <QTimeZone>
#include <unistd.h>

namespace {
bool selectComboRowWithKeys(QComboBox* combo, int row) {
    if (!combo || !combo->isVisible() || !combo->isEnabled() || row<0 || row>=combo->count()) return false;
    // A tall, styled popup can place its row rectangle outside the actual
    // screen even after scrollTo(). Use real native keyboard navigation;
    // never mutate its model/current index or invoke installer decisions.
    QTest::mouseClick(combo, Qt::LeftButton);
    auto* view=combo->view();
    if (!view->isVisible()) return false;
    QTest::keyClick(view, Qt::Key_Home);
    for (int index=0; index<row; ++index) QTest::keyClick(view, Qt::Key_Down);
    QTest::keyClick(view, Qt::Key_Return);
    return combo->currentIndex()==row;
}

QString readFile(const QString& path) {
    QFile file(path);
    return file.open(QIODevice::ReadOnly) ? QString::fromUtf8(file.readAll()).trimmed() : QString();
}
QQuickItem* itemWithProperty(QQuickItem* root, const char* property) {
    if (root->property(property).isValid()) return root;
    for (auto* child : root->childItems())
        if (auto* found = itemWithProperty(child, property)) return found;
    return nullptr;
}
QQuickItem* namedItem(QQuickItem* root, const QString& name) {
    if (root->objectName() == name) return root;
    for (auto* child : root->childItems())
        if (auto* found = namedItem(child, name)) return found;
    return nullptr;
}

QJsonObject modalDetails(QWidget* widget) {
    QStringList text;
    if (auto* box = qobject_cast<QMessageBox*>(widget)) {
        text << box->text() << box->informativeText() << box->detailedText();
    } else {
        for (auto* label : widget->findChildren<QLabel*>()) text << label->text();
    }
    // Never inspect editable controls, especially account/password fields.
    return {{"title", widget->windowTitle()}, {"class", widget->metaObject()->className()},
            {"text", text.join('\n').left(16384)}};
}

class ModalWatchdog {
    QPointer<QWidget> current;
    qint64 since = -1;
public:
    bool isCurrent(QWidget* widget) const { return current.data() == widget; }
    void reset() { current.clear(); since = -1; }
    bool observe(QWidget* widget, qint64 now) {
        if (!widget) { reset(); return false; }
        if (!isCurrent(widget) || since < 0) { current = widget; since = now; }
        return now - since >= 30000;
    }
};

class Driver : public QObject {
    QString logPath = qEnvironmentVariable("HUSK_INSTALL_DRIVER_LOG");
    QString user = qEnvironmentVariable("HUSK_INSTALL_TEST_USER");
    QString password = qEnvironmentVariable("HUSK_INSTALL_TEST_PASSWORD");
    bool cancelMode = qEnvironmentVariable("HUSK_INSTALL_TEST_MODE") == "cancel";
    QTimer timer;
    QElapsedTimer elapsed, pageTime;
    ModalWatchdog unexpectedModal;
    QSet<int> advanced;
    int lastPage = -1, countdownStart = -1;
    qint64 confirmationAt = -1, finishAt = -1;
    bool stopped = false, diskInitial = false, diskSelected = false;
    bool eraseSelected = false, usersEntered = false, summarySeen = false;
    bool zoneClockChosen = false, zoneSelected = false;
    bool confirmationSeen = false, confirmationClicked = false, finishSeen = false;
    bool cancelRequested = false;

    void record(const QString& event, QJsonObject values = {}) {
        values.insert("event", event);
        values.insert("elapsed_ms", elapsed.elapsed());
        values.insert("time", QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs));
        QFile file(logPath);
        if (!file.open(QIODevice::WriteOnly | QIODevice::Append)) { qApp->exit(86); return; }
        file.write(QJsonDocument(values).toJson(QJsonDocument::Compact) + '\n');
        file.flush();
    }
    void fail(const QString& message) {
        if (stopped) return;
        stopped = true; timer.stop();
        record("driver-failed", {{"message", message}});
        qApp->exit(85);
    }
    static QString labels(QWidget* root) {
        QStringList result;
        for (auto* label : root->findChildren<QLabel*>()) result.append(label->text());
        return result.join('\n');
    }
    void click(QWidget* widget) {
        QPointer<QWidget> target(widget);
        // The queued event allows the timer to inspect a real nested modal
        // confirmation while the clicked button's handler is in exec().
        QTimer::singleShot(0, this, [target] {
            if (target && target->isVisible() && target->isEnabled())
                QTest::mouseClick(target, Qt::LeftButton, Qt::NoModifier, target->rect().center());
        });
    }
    bool fill(QWidget* page, const char* name, const QString& value) {
        auto* input = page->findChild<QLineEdit*>(QString::fromLatin1(name));
        if (!input || !input->isVisible() || !input->isEnabled()) return false;
        QTest::mouseClick(input, Qt::LeftButton);
        QTest::keyClick(input, Qt::Key_A, Qt::ControlModifier);
        QTest::keyClicks(input, value);
        return input->text() == value;
    }
    bool modal() {
        auto* widget = QApplication::activeModalWidget();
        if (!widget) { unexpectedModal.reset(); return false; }
        auto* box = qobject_cast<QMessageBox*>(widget);
        const bool cancelling = box && cancelMode && box->windowTitle().contains("Cancel Installation");
        const bool confirming = box && box->windowTitle().contains("Continue with Installation");
        if (!cancelling && !confirming) {
            const auto details = modalDetails(widget);
            if (!unexpectedModal.isCurrent(widget)) record("unexpected-modal", details);
            if (unexpectedModal.observe(widget, elapsed.elapsed()))
                fail("Unhandled installer dialog: " + details.value("title").toString() + ": " +
                     details.value("text").toString());
            return true;
        }
        unexpectedModal.reset();
        if (box && cancelMode && box->windowTitle().contains("Cancel Installation")) {
            if (!summarySeen || !cancelRequested) {
                fail("Cancellation confirmation appeared before the reviewed summary"); return true;
            }
            auto* yes = qobject_cast<QPushButton*>(box->button(QMessageBox::Yes));
            if (!yes || !yes->isEnabled()) { fail("The real cancellation confirmation is unavailable"); return true; }
            record("cancel-confirmed", {{"text",box->text()}});
            stopped = true; timer.stop(); click(yes); return true;
        }
        if (!box || !box->windowTitle().contains("Continue with Installation")) return true;
        if (!summarySeen || !diskSelected || !eraseSelected || !usersEntered) {
            fail("An installation confirmation appeared before the reviewed choices"); return true;
        }
        if (!box->text().contains("not be able", Qt::CaseInsensitive)) {
            fail("The final confirmation did not explain irreversible disk changes"); return true;
        }
        QPushButton* install = nullptr;
        for (auto* button : box->findChildren<QPushButton*>())
            if (QString(button->text()).remove('&') == "Install Now") install = button;
        if (!install || !install->isEnabled()) return true;
        if (!confirmationSeen) {
            confirmationSeen = true; confirmationAt = elapsed.elapsed();
            record("confirmation-shown", {{"title", box->windowTitle()}, {"text", box->text()}});
        }
        if (!confirmationClicked && elapsed.elapsed() - confirmationAt >= 4000) {
            confirmationClicked = true;
            record("confirmation-click", {{"button", "Install Now"}}); click(install);
        }
        return true;
    }
    void partition(QWidget* page, QPushButton* next) {
        QComboBox* drive = nullptr;
        QJsonArray devices;
        for (auto* combo : page->findChildren<QComboBox*>()) {
            for (int row = 0; row < combo->count(); ++row) {
                const QString text = combo->itemText(row);
                if (text.contains("/dev/")) { drive = combo; devices.append(text); }
            }
        }
        if (!drive) return; // Real device scanning may still be running.
        const QString target = devices.size() == 1 ? devices[0].toString() : QString();
        if (devices.size() != 1 || !(target == "/dev/vda" || target.endsWith("(/dev/vda)")) || drive->count() != 1) {
            fail("The production disk guard did not expose exactly the disposable /dev/vda target"); return;
        }
        if (!diskInitial) {
            if (drive->currentIndex() != -1 || next->isEnabled()) {
                fail("The installation drive was preselected or Next was enabled before selection"); return;
            }
            diskInitial = true;
            record("drive-no-selection", {{"devices", devices}, {"next_enabled", false}});
            if (!selectComboRowWithKeys(drive, 0)) { fail("The actual drive choice could not be selected"); return; }
            return;
        }
        if (!diskSelected && drive->currentIndex() == 0) {
            diskSelected = true; record("drive-selected", {{"device", "/dev/vda"}, {"label", drive->currentText()}});
        }
        if (!diskSelected) return;
        QRadioButton* erase = nullptr;
        for (auto* radio : page->findChildren<QRadioButton*>())
            if (radio->isVisible() && labels(radio->parentWidget()).contains("Erase disk")) erase = radio;
        if (!erase) return;
        if (!eraseSelected) {
            if (erase->isChecked()) { fail("Erase was selected without a new explicit activation"); return; }
            eraseSelected = true; record("erase-selected", {{"device", "/dev/vda"}}); click(erase); return;
        }
        if (erase->isChecked() && next->isEnabled() && !advanced.contains(3)) {
            advanced.insert(3); click(next);
        }
    }
    void finished() {
        for (auto* window : QGuiApplication::allWindows()) {
            auto* quick = qobject_cast<QQuickWindow*>(window);
            if (!quick || !quick->isVisible()) continue;
            auto* root = itemWithProperty(quick->contentItem(), "secondsRemaining");
            if (!root) continue;
            auto* title = namedItem(root, "husk-finish-title");
            auto* later = namedItem(root, "husk-restart-later");
            if (!title || !later) continue;
            if (title->property("text").toString() != "Installation Complete") {
                fail("Calamares did not report a successful real installation"); return;
            }
            const int seconds = root->property("secondsRemaining").toInt();
            if (!finishSeen) {
                if (seconds < 25 || seconds > 30) { fail("The real thirty-second countdown was unavailable"); return; }
                finishSeen = true; finishAt = elapsed.elapsed(); countdownStart = seconds;
                record("installation-success", {{"title", title->property("text").toString()}, {"seconds", seconds}});
            }
            if (elapsed.elapsed() - finishAt >= 4000 && seconds <= countdownStart - 2 && seconds > 0) {
                if (!later->isVisible() || !later->isEnabled()) { fail("Restart Later is not actionable"); return; }
                record("countdown-observed", {{"first", countdownStart}, {"last", seconds},
                                              {"observed_ms", elapsed.elapsed() - finishAt}});
                record("restart-later-click"); stopped = true; timer.stop();
                const QPoint center = later->mapToScene(QPointF(later->width()/2, later->height()/2)).toPoint();
                QTest::mouseClick(quick, Qt::LeftButton, Qt::NoModifier, center);
            }
            return;
        }
    }
    void tick() {
        if (stopped) return;
        if (elapsed.elapsed() > 2400000) { fail("The real installer exceeded its forty-minute deadline"); return; }
        if (modal()) return;
        QStackedWidget* stack = nullptr;
        QPushButton* next = nullptr;
        QPushButton* cancel = nullptr;
        for (auto* widget : QApplication::allWidgets()) {
            if (widget->objectName() == "viewManagerStack") stack = qobject_cast<QStackedWidget*>(widget);
            if (widget->objectName() == "view-button-next") next = qobject_cast<QPushButton*>(widget);
            if (widget->objectName() == "view-button-cancel") cancel = qobject_cast<QPushButton*>(widget);
        }
        if (!stack || !next || !stack->isVisible()) {
            if (elapsed.elapsed() > 180000) {
                QStringList windows;
                for (auto* window : QApplication::topLevelWidgets())
                    if (window->isVisible()) windows << window->windowTitle();
                fail("The expected Calamares navigation did not become visible: " + windows.join(", "));
            }
            return;
        }
        if (stack->count() != 8) {
            if (elapsed.elapsed() > 180000)
                fail("Unexpected Calamares page sequence; refusing to automate disk changes");
            return; // The production module loader inserts views asynchronously.
        }
        const int index = stack->currentIndex();
        auto* page = stack->currentWidget();
        const char* names[] = {"welcome", "keyboard", "locale", "partition", "users", "summary", "execution", "finished"};
        if (index < 0 || index > 7 || !page) { fail("The current Calamares page is unavailable"); return; }
        if (index != lastPage) {
            lastPage = index; pageTime.restart();
            record(QString("page-") + names[index], {{"class", page->metaObject()->className()}, {"object", page->objectName()}});
        }
        // Leave each decision page on screen long enough for the independent
        // VM monitor to capture it. Readiness/selection checks still apply.
        if (index < 6 && pageTime.elapsed() < 1800) return;
        if (index != 6 && index != 7 && pageTime.elapsed() > 180000) {
            fail(QString("The real ") + names[index] + " page did not become actionable"); return;
        }
        if (index == 3) { partition(page, next); return; }
        if (index == 2 && !zoneSelected) {
            const QByteArray zone("Europe/Helsinki");
            const int offset = QTimeZone(zone).offsetFromUtc(QDateTime::currentDateTimeUtc());
            if (!zoneClockChosen) {
                if (next->isEnabled()) { fail("Time zone Next was enabled without a named region"); return; }
                auto* clock = page->findChild<QPushButton*>(QString("husk-offset-%1").arg(offset));
                if (!clock) { fail("The real Helsinki clock offset was unavailable"); return; }
                for (auto* scroll : page->findChildren<QScrollArea*>())
                    if (scroll->isAncestorOf(clock)) scroll->ensureWidgetVisible(clock);
                zoneClockChosen = true; click(clock); return;
            }
            auto* regions = page->findChild<QComboBox*>("husk-region");
            const int row = regions ? regions->findData(QString::fromLatin1(zone)) : -1;
            if (!regions || row < 1) { fail("The chosen clock did not expose the proper IANA region"); return; }
            if (!selectComboRowWithKeys(regions,row) || regions->currentData().toString() != QString::fromLatin1(zone)) {
                fail("Actual keyboard selection did not choose Europe/Helsinki"); return;
            }
            zoneSelected = true;
            record("timezone-selected", {{"iana",QString::fromLatin1(zone)},{"current_offset",offset}});
            return;
        }
        if (index == 4 && !usersEntered) {
            auto* autologin = page->findChild<QCheckBox*>("checkBoxDoAutoLogin");
            if (!autologin || autologin->isChecked()) { fail("The acceptance account must require a real login"); return; }
            if (!fill(page, "textBoxFullName", "Husk Acceptance") || !fill(page, "textBoxLoginName", user) ||
                !fill(page, "textBoxHostname", "husk-v3-check") || !fill(page, "textBoxUserPassword", password) ||
                !fill(page, "textBoxUserVerifiedPassword", password)) { fail("Actual user fields could not be filled"); return; }
            password.fill('x'); password.clear(); usersEntered = true;
            record("users-entered", {{"user", user}, {"autologin", false}}); return;
        }
        if (index == 5 && !summarySeen) {
            const QString text = labels(page);
            if (!text.contains("/dev/vda") || !text.contains(user) || text.contains("/dev/sr0")) {
                fail("The actual summary did not identify the selected target and account"); return;
            }
            summarySeen = true; record("summary-reviewed", {{"text", text}});
        }
        if (index == 5 && cancelMode) {
            if (!cancelRequested && pageTime.elapsed() >= 4000) {
                if (!cancel || !cancel->isVisible() || !cancel->isEnabled()) {
                    fail("The summary page did not allow cancelling before disk writes"); return;
                }
                cancelRequested = true; record("cancel-click"); click(cancel);
            }
            return;
        }
        if (index == 6) {
            if (!confirmationClicked) fail("Execution began without the separate explicit confirmation");
            return;
        }
        if (index == 7) {
            if (!finishSeen && pageTime.elapsed() > 90000)
                fail("The actual completion page did not expose its success/countdown controls");
            else finished();
            return;
        }
        if (index == 1 && !advanced.contains(1)) {
            auto* layouts = page->findChild<QListView*>("layoutSelector");
            if (!layouts || !layouts->model()) return;
            bool chosen = false;
            for (int row = 0; row < layouts->model()->rowCount(); ++row) {
                const QModelIndex item = layouts->model()->index(row, 0);
                if (item.data().toString() == "English (US)") {
                    layouts->scrollTo(item); QTest::mouseClick(layouts->viewport(), Qt::LeftButton,
                        Qt::NoModifier, layouts->visualRect(item).center());
                    chosen = layouts->currentIndex() == item; break;
                }
            }
            if (!chosen) { fail("The real English (US) keyboard selection was unavailable"); return; }
        }
        if (next->isVisible() && next->isEnabled() && !advanced.contains(index) &&
            (index != 5 || pageTime.elapsed() >= 4000)) {
            advanced.insert(index); click(next);
        }
    }
public:
    Driver() {
        elapsed.start(); pageTime.start();
        // Child backend processes must never inherit the preload or password.
        qunsetenv("LD_PRELOAD"); qunsetenv("HUSK_INSTALL_TEST_PASSWORD");
        const QString serial = readFile("/sys/class/block/vda/serial");
        if (getuid() != 0 || !QFile::exists("/run/archiso/bootmnt/arch/x86_64/airootfs.sfs") ||
            !QFile::exists("/sys/firmware/efi") || readFile("/run/husk-v3-disposable-test") != "HUSK-DISPOSABLE" ||
            serial != "HUSK-DISPOSABLE" || user.isEmpty() || password.size() < 16 || logPath.isEmpty()) {
            fail("The test driver requires the explicitly marked disposable UEFI Live guest"); return;
        }
        record("driver-started", {{"qt", qVersion()}, {"serial", serial},
            {"calamares_log", QStandardPaths::writableLocation(QStandardPaths::CacheLocation) + "/session.log"}});
        connect(qApp, &QCoreApplication::aboutToQuit, this, [this] { record("application-quit"); });
        connect(&timer, &QTimer::timeout, this, [this] { tick(); }); timer.start(500);
    }
};

void startup() {
    if (qEnvironmentVariable("HUSK_INSTALL_ACCEPTANCE") != "1") return;
    QTimer::singleShot(1000, QCoreApplication::instance(), [] { new Driver; });
}
Q_COREAPP_STARTUP_FUNCTION(startup)
} // namespace
