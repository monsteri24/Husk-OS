import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
Rectangle {
  color: "#0b1321"
  ColumnLayout {
    anchors.centerIn: parent; width: 380; spacing: 18
    Label { text: "Husk OS"; color: "#eaf1ff"; font.pixelSize: 46; Layout.alignment: Qt.AlignHCenter }
    Label { text: "Experimental · system-1"; color: "#8fb9f4"; Layout.alignment: Qt.AlignHCenter }
    TextField { id: loginName; Layout.fillWidth: true; placeholderText: "Käyttäjänimi"; text: userModel.lastUser }
    TextField { id: password; Layout.fillWidth: true; placeholderText: "Salasana";
                echoMode: TextInput.Password; focus: true; onAccepted: sddm.login(loginName.text, password.text, session.currentIndex) }
    ComboBox { id: session; Layout.fillWidth: true; model: sessionModel; textRole: "name"; currentIndex: sessionModel.lastIndex }
    Label { id: message; text: ""; color: "#ffb7b7"; wrapMode: Text.Wrap; Layout.fillWidth: true }
    Button { text: "Kirjaudu sisään"; Layout.fillWidth: true; onClicked: sddm.login(loginName.text, password.text, session.currentIndex) }
    RowLayout {
      Button { text: "Lepotila"; onClicked: sddm.suspend() }
      Button { text: "Käynnistä uudelleen"; onClicked: sddm.reboot() }
      Button { text: "Sammuta"; onClicked: sddm.powerOff() }
    }
  }
  Connections { target: sddm; function onLoginFailed() { message.text = "Kirjautuminen ei onnistunut."; password.text = ""; } }
}
