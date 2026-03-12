#include "MainWidget.h"
#include "SettingsWidget.h"
#include "SystemTray.h"

#include <QtWidgets/QApplication>
#include <QDebug>
#include <QString>
#include <QJsonObject>

#include <GlobalInclude.h>

// 获取全局变量配置
void getConfig()
{
    // 获取config.json文件路径并加载Json对象
    _global_config = new JsonOperation("Config/config.json");
}

QString getDict() {
    // 加载字典文件并解析为Json对象
    QString dict_path = GET_STRING_FROM_JSON(_global_config, "settings", "dict_path");
    _global_dict = new JsonOperation(dict_path);
    // 判断语言
    if (dict_path.endsWith("zh.json", Qt::CaseInsensitive)) return "Chinese";
    if (dict_path.endsWith("en.json", Qt::CaseInsensitive)) return "English";
}

// 主函数：程序入口
int main(int argc, char *argv[])
{
	// 输出启动信息
	qDebug() << "ദ്ദി˶˃ ᵕ ˂ )✧ [Qt Operation]Starting application...";

    // 设置OpenGL格式支持透明
    QSurfaceFormat format;
    format.setAlphaBufferSize(8);
    format.setSamples(4);
    QSurfaceFormat::setDefaultFormat(format);

	// 创建应用程序对象
    QApplication app(argc, argv);

    // 加载配置
    getConfig();

    // 加载字典
    qDebug() << "ദ്ദി˶˃ ᵕ ˂ )✧ [Qt Operation]Load dictionary succeed! Changing to language: " <<getDict();

    // 设置应用程序信息
	app.setApplicationName(GET_STRING_FROM_JSON(_global_dict, "application_data", "application_name")); // 设置应用程序名称
    app.setApplicationVersion("0.0.1"); // 设置版本
    app.setWindowIcon(QIcon(GET_STRING_FROM_JSON(_global_config, "settings", "icon_path")));    // 设置图标
	app.setQuitOnLastWindowClosed(false);   // 设置关闭最后一个窗口时不退出应用程序

	// 创建主界面对象并显示
    MainWidget mainWidget;
    mainWidget.show();

    // 创建设置界面对象
    SettingsWidget settingsWidget;

    // 创建托盘菜单类
    SystemTray systemTray(mainWidget, settingsWidget);

    // 开始应用程序循环
	qDebug().noquote() << "ദ്ദി˶˃ ᵕ ˂ )✧ [Qt Operation]Starting application loop...";
    return app.exec();
}
