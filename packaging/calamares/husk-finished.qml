// SPDX-License-Identifier: GPL-3.0-or-later
import io.calamares.core 1.0
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Page {
    id: finished
    width: parent ? parent.width : 800
    height: parent ? parent.height : 600

    property int secondsRemaining: 30
    property bool activatedInCalamares: false
    property bool postponed: false
    property bool restartRequested: false

    function restartNow() {
        restartTimer.stop()
        config.restartNowWanted = false
        if (config.failed || postponed || restartRequested)
            return
        restartRequested = true
        config.doRestart(true)
    }

    function restartLater() {
        restartTimer.stop()
        postponed = true
        config.restartNowWanted = false
        ViewManager.quit()
    }

    function onActivate() {
        restartTimer.stop()
        config.restartNowWanted = false
        if (config.failed || postponed || restartRequested)
            return
        secondsRemaining = 30
        restartTimer.start()
    }

    function onLeave() {
        restartTimer.stop()
        config.restartNowWanted = false
    }

    Timer {
        id: restartTimer
        objectName: "husk-restart-timer"
        interval: 1000
        repeat: true
        running: false
        onTriggered: {
            if (config.failed || finished.postponed || finished.restartRequested) {
                stop()
                return
            }
            finished.secondsRemaining = Math.max(0, finished.secondsRemaining - 1)
            if (finished.secondsRemaining === 0)
                finished.restartNow()
        }
    }

    Connections {
        target: config
        function onFailureChanged() {
            if (config.failed)
                restartTimer.stop()
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 720)
        spacing: 24

        Label {
            objectName: "husk-finish-title"
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 30
            font.bold: true
            text: config.failed ? "Installation Failed" : "Husk OS is Ready"
        }

        Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: config.failed
                ? "Husk OS could not be installed. Your installation has not completed successfully."
                : "Husk OS has been installed. Remove the installation media when the computer restarts."
        }

        Label {
            Layout.fillWidth: true
            visible: config.failed
            wrapMode: Text.WordWrap
            textFormat: Text.PlainText
            text: config.failureMessage + "\n" + config.failureDetails
        }

        Label {
            Layout.fillWidth: true
            visible: !config.failed
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: 22
            text: "Restarting in " + finished.secondsRemaining + " seconds"
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            layoutDirection: Qt.LeftToRight
            spacing: 24

            Button {
                objectName: "husk-restart-later"
                text: "Restart Later"
                Layout.minimumWidth: 160
                onClicked: finished.restartLater()
            }

            Button {
                objectName: "husk-restart-now"
                text: "Restart Now"
                Layout.minimumWidth: 160
                enabled: !config.failed && !finished.restartRequested
                onClicked: finished.restartNow()
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            text: "The installation log is available in the Live user's home directory."
        }
    }
}
