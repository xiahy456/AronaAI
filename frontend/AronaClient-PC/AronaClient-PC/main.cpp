#include "GLCore.h"
#include "MainWidget.h"
#include <QtWidgets/QApplication>

int main(int argc, char *argv[])
{
    // 实例化应用程序对象
    QApplication app(argc, argv);

    // 设置应用程序信息
    app.setApplicationName("AronaClient");
    app.setApplicationVersion("alpha0.0.1");
    app.setQuitOnLastWindowClosed(false); // 禁用关闭最后一个窗口时退出应用

    // GLCore对象实例化、显示
    GLCore gLCore;
    gLCore.show();
    // 主界面对象实例化
    MainWidget mainWidget;
    //mainWidget.show();

    // 进入应用程序主循环
    return app.exec();
}
