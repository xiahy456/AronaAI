#include "GLCore.h"
#include <QtWidgets/QApplication>

int main(int argc, char *argv[])
{
    // 实例化应用程序对象
    QApplication app(argc, argv);

    // 主界面对象实例化、显示
    GLCore window;
    window.show();

    // 进入应用程序主循环
    return app.exec();
}
