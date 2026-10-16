import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Rectangle {
  color: "#0b1321"
  ColumnLayout {
    anchors.centerIn: parent; width: 380; spacing: 18
    Label { text: qsTr("Husk OS"); color: "#eaf1ff"; font.pixelSize: 46; Layout.alignment: Qt.AlignHCenter }
    Label { text: qsTr("Experimental · system-2"); color: "#8fb9f4"; Layout.alignment: Qt.AlignHCenter }
    TextField { id: loginName; Layout.fillWidth: true; placeholderText: qsTr("Username"); text: userModel.lastUser }
    TextField { id: password; Layout.fillWidth: true; placeholderText: qsTr("Password");
                echoMode: TextInput.Password; focus: true; onAccepted: sddm.login(loginName.text, password.text, session.currentIndex) }
    ComboBox { id: session; Layout.fillWidth: true; model: sessionModel; textRole: "name"; currentIndex: sessionModel.lastIndex }
    Label { id: message; text: ""; color: "#ffb7b7"; wrapMode: Text.Wrap; Layout.fillWidth: true }
    Button { text: qsTr("Log in"); Layout.fillWidth: true; onClicked: sddm.login(loginName.text, password.text, session.currentIndex) }
    RowLayout {
      Button { text: qsTr("Suspend"); onClicked: sddm.suspend() }
      Button { text: qsTr("Restart"); onClicked: sddm.reboot() }
      Button { text: qsTr("Power off"); onClicked: sddm.powerOff() }
    }
  }
  Connections { target: sddm; function onLoginFailed() { message.text = qsTr("Login failed."); password.text = ""; } }
}
