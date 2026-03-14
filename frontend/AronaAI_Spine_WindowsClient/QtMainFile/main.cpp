/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

#include "MainWidget.h"
#include "SettingsWidget.h"
#include "SystemTray.h"
#include "MainController.h"
#include "TTSManager.h"
#include "AudioRecorder.h"
#include "SpeechRecognizer.h"
#include "ShortCutKey.h"

#include <QtWidgets/QApplication>
#include <QDebug>
#include <QString>
#include <QJsonObject>
#include <QElapsedTimer>

#include <GlobalInclude.h>

// 获取全局配置
void getConfig()
{
    _global_config = new JsonOperation("Config/config.json");
}

QString getDict() {
	// 获取字典路径并加载字典
    QString dict_path = GET_STRING_FROM_JSON(_global_config, "settings", "dict_path");
    _global_dict = new JsonOperation(dict_path);
	// 识别语言类型并返回语言名称
    if (dict_path.endsWith("zh.json", Qt::CaseInsensitive)) return "Chinese";
    if (dict_path.endsWith("en.json", Qt::CaseInsensitive)) return "English";
}

// 程序入口 main函数
int main(int argc, char *argv[])
{
	// 输出启动信息
	qDebug().noquote() << FINE_PR << "[Qt Operation]Starting application...";

	// 设置OpenGL格式，启用抗锯齿和透明度支持
    QSurfaceFormat format;
    format.setAlphaBufferSize(8);
    format.setSamples(4);
    QSurfaceFormat::setDefaultFormat(format);

	// 创建应用程序对象
    QApplication app(argc, argv);

    // 获取配置信息
    getConfig();

    // 获取字典信息
    qDebug().noquote() << FINE_PR << "[Qt Operation]Load dictionary succeed! Changing to language: " <<getDict();

    // 应用程序设置
	app.setApplicationName(GET_STRING_FROM_JSON(_global_dict, "application_data", "application_name")); // 设置应用程序名称
	app.setApplicationVersion("0.0.1"); // 设置应用程序版本
	app.setWindowIcon(QIcon(GET_STRING_FROM_JSON(_global_config, "settings", "icon_path")));    // 设置应用程序图标
	app.setQuitOnLastWindowClosed(false);   // 设置当最后一个窗口关闭时不退出应用程序
    qputenv("QT_FRAME_RATE_OVERRIDE", QByteArray::number(GET_INT_FROM_JSON(_global_config, "settings", "frame_rate")));    // 设置全局帧率

	// 创建主窗口对象并显示
    MainWidget* mainWidget = new MainWidget;
    mainWidget->show();

	// 创建设置窗口对象
    SettingsWidget* settingsWidget = new SettingsWidget;

    // 创建TTS对象
	TTSManager* ttsManager = new TTSManager;

    // 创建声音录制对象
	AudioRecorder* audioRecorder = new AudioRecorder;

	// 创建腾讯语音识别对象
    TencentSpeechRecognizer* tencentSpeechRecognizer = new TencentSpeechRecognizer;

    // 创建主控制对象
	MainController* mainController = new MainController(mainWidget, ttsManager, audioRecorder, tencentSpeechRecognizer);

	// 创建快捷键对象
	ShortCutKey* shortCutKey = new ShortCutKey(mainController);

    // 鍒涘缓鎵樼洏鑿滃崟绫?
    SystemTray* systemTray = new SystemTray(mainWidget, settingsWidget);

	// 开始应用程序事件循环
	qDebug().noquote() << FINE_PR << "[Qt Operation]Starting application loop...";
    return app.exec();
}
