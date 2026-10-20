"""Exercise VM login keys against the actual SDDM theme, without PAM or a VM."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class SddmInputTests(unittest.TestCase):
    def test_real_theme_keyboard_sequence_selects_husk_and_fills_the_correct_fields(self):
        flags=subprocess.run(['pkg-config','--cflags','--libs','Qt6Quick','Qt6Qml','Qt6Test'],capture_output=True,text=True)
        if flags.returncode: self.skipTest('Qt6 Quick development packages unavailable')
        spec=importlib.util.spec_from_file_location('login_harness',ROOT/'scripts/ci-test-v3-install.py')
        harness=importlib.util.module_from_spec(spec); spec.loader.exec_module(harness)
        actions=[]
        monitor=SimpleNamespace(key=lambda value:actions.append(dict(kind='key',value=value)),
            type_text=lambda value:actions.append(dict(kind='text',value=value)))
        context=SimpleNamespace(auth_started=False,monitor=monitor,args=SimpleNamespace(username='huskcheck'),password='TestOnlyV3Password')
        with patch.object(harness.time,'sleep'): harness.Acceptance.sddm_login(context)
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary); source=directory/'login.cpp'; binary=directory/'login'
            source.write_text(r'''
#include <QGuiApplication>
#include <QQuickView>
#include <QQmlComponent>
#include <QQmlContext>
#include <QFile>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QTest>
#include <memory>
int main(int argc,char**argv) {
    QGuiApplication app(argc,argv); QQuickView view;
    QQmlComponent component(view.engine());
    component.setData(R"QML(import QtQuick
QtObject {
 property string lastUser: ""
 property string loggedUser: ""
 property string loggedPassword: ""
 property int loggedSession: -1
 property QtObject sessions: ListModel {
  property int lastIndex: 0
  ListElement { name: "labwc" }
  ListElement { name: "Husk Desktop (Experimental)" }
 }
 signal loginFailed()
 function login(user,password,session) { loggedUser=user; loggedPassword=password; loggedSession=session }
})QML",QUrl());
    std::unique_ptr<QObject> mock(component.create());
    if (!mock) return 1;
    view.rootContext()->setContextProperty("userModel",mock.get());
    view.rootContext()->setContextProperty("sddm",mock.get());
    view.rootContext()->setContextProperty("sessionModel",mock->property("sessions").value<QObject*>());
    view.setResizeMode(QQuickView::SizeRootObjectToView); view.resize(1280,800);
    view.setSource(QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2])));
    if (view.status()!=QQuickView::Ready) return 2;
    view.show(); view.requestActivate(); QTest::qWait(100);
    QFile file(QString::fromLocal8Bit(argv[1])); if (!file.open(QIODevice::ReadOnly)) return 3;
    for (const auto& entry:QJsonDocument::fromJson(file.readAll()).array()) {
        const auto action=entry.toObject(); const QString value=action.value("value").toString();
        if (action.value("kind")=="text") {
            for (const QChar character:value) QTest::keyClick(&view,character.toLatin1());
        } else if (value=="tab") QTest::keyClick(&view,Qt::Key_Tab);
        else if (value=="shift-tab") QTest::keyClick(&view,Qt::Key_Tab,Qt::ShiftModifier);
        else if (value=="ctrl-a") QTest::keyClick(&view,Qt::Key_A,Qt::ControlModifier);
        else if (value=="home") QTest::keyClick(&view,Qt::Key_Home);
        else if (value=="h") QTest::keyClick(&view,Qt::Key_H);
        else if (value=="ret") QTest::keyClick(&view,Qt::Key_Return);
        else if (value=="ctrl-alt-f1") QTest::keyClick(&view,Qt::Key_F1,Qt::ControlModifier|Qt::AltModifier);
        else return 4;
        QCoreApplication::processEvents();
    }
    if (mock->property("loggedSession").toInt()!=1) return 5;
    if (mock->property("loggedUser")!="huskcheck") return 6;
    if (mock->property("loggedPassword")!="TestOnlyV3Password") return 7;
    return 0;
}
''')
            built=subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fPIC',str(source),'-o',str(binary),*shlex.split(flags.stdout)],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            commands=directory/'actions.json'; commands.write_text(json.dumps(actions))
            environment=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_QUICK_CONTROLS_STYLE='Basic')
            if environment.get('HUSK_TEST_SYSROOT'):
                prefix=Path(environment['HUSK_TEST_SYSROOT'])/'usr/lib/x86_64-linux-gnu/qt6'
                environment.update(QT_PLUGIN_PATH=str(prefix/'plugins'),QML_IMPORT_PATH=str(prefix/'qml'),QML2_IMPORT_PATH=str(prefix/'qml'))
            for style in ('Basic','Fusion'):
                with self.subTest(style=style):
                    result=subprocess.run([str(binary),str(commands),str(ROOT/'branding/sddm/Main.qml')],
                        env=dict(environment,QT_QUICK_CONTROLS_STYLE=style),capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0,'Actual greeter input failed: '+result.stderr)
