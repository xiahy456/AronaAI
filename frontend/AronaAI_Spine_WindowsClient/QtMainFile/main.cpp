#include "MainWidget.h"
#include <QtWidgets/QApplication>

// 主函数：程序入口
int main(int argc, char *argv[])
{
	// 创建应用程序对象
    QApplication app(argc, argv);

	// 创建主窗口对象并显示
    MainWidget window;
    window.show();

    // 开始应用程序循环
    return app.exec();
}
