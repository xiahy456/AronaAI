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

#include "Defines.h"
#include "MainWidget.h"
#include "SettingsWidget.h"
#include "UserInputWidget.h"
#include "SystemTray.h"
#include "MainController.h"
#include "TTSManager.h"
#include "AudioRecorder.h"
#include "TencentSpeechRecognizer.h"
#include "ShortCutKey.h"
#include "BlueakaFontLoader.h"
#include "WebSocketController.h"

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

// 获取字典
QString getDict() {
	// 获取字典路径并加载字典
    QString dict_path = GET_STRING_FROM_JSON(_global_config, "settings", "dict_path");
    _global_dict = new JsonOperation(dict_path);
	// 识别语言类型并返回语言名称
    if (dict_path.endsWith("zh.json", Qt::CaseInsensitive)) return "Chinese";
    if (dict_path.endsWith("en.json", Qt::CaseInsensitive)) return "English";
}

// 加载Blueaka字体
void loadBlueakaFont() {
    QString blueaka_fontDir = GET_STRING_FROM_JSON(_global_config, "settings", "font_path");
    if (BlueakaFontLoader::instance()->loadFromDirectory(blueaka_fontDir)) {
        FINE_DEBUG_OUTPUT("[Font Loader]Fonts loaded successfully!");
        FINE_DEBUG_OUTPUT("[Font Loader]Head of font families:" + BlueakaFontLoader::instance()->getFontFamilies()[0]);
    }
    else {
        ERROR_DEBUG_OUTPUT("[Font Loader]Failed to load Blueaka fonts, using system fonts");
    }
}

// 程序入口main函数
int main(int argc, char *argv[])
{
    // 输出启动信息
    FINE_DEBUG_OUTPUT("[Qt Operation]Starting application...");

	// 设置OpenGL格式，启用抗锯齿和透明度支持
    OPENGL_INITIALLIZE;

	// 创建应用程序对象
    QApplication app(argc, argv);

    // 获取配置信息
    getConfig();

    // 获取字典信息
    FINE_DEBUG_OUTPUT("[Qt Operation]Load dictionary succeed! Changing to language: " + getDict());

    // 应用程序初始化
    APPLICATION_INITIALLIZE;

    // 加载Blueaka字体
    loadBlueakaFont();

	// 创建主窗口对象
    MainWidget* mainWidget = new MainWidget;

	// 创建设置窗口对象
    SettingsWidget* settingsWidget = new SettingsWidget;

    // 创建用户输入窗口对象
    UserInputWidget* userInputWidget = new UserInputWidget;

    // 创建TTS对象
	TTSManager* ttsManager = new TTSManager;

    // 创建声音录制对象
	AudioRecorder* audioRecorder = new AudioRecorder;

	// 创建腾讯语音识别对象
    TencentSpeechRecognizer* tencentSpeechRecognizer = new TencentSpeechRecognizer;

	// 创建WebSocket控制器对象
    WebSocketController* webSocketController = new WebSocketController;

    // 创建主控制对象
	MainController* mainController = new MainController(mainWidget, ttsManager, audioRecorder, tencentSpeechRecognizer, webSocketController, userInputWidget);

	// 创建快捷键对象
	ShortCutKey* shortCutKey = new ShortCutKey(mainController);

    // 创建系统托盘类对象
    SystemTray* systemTray = new SystemTray(mainWidget, settingsWidget);

    // 输出信息必要类实例化完毕，准备启动应用程序事件循环
    FINE_DEBUG_OUTPUT("[Qt Operation]Necessary class instantiation complete! Starting application loop...");

    // 界面显示
    mainWidget->show();
    if (GET_BOOL_FROM_JSON(_global_config, "settings", "open_setting_widget")) settingsWidget->show();

    // 开始应用程序事件循环
    return app.exec();
}
