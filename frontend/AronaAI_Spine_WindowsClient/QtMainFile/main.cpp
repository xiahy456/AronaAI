#include "MainWidget.h"
#include <QtWidgets/QApplication>
#include <spine/QtSkeletonLoader.h>
#include <spine/QtSpineManager.h>
#include <QDebug>

// 主函数：程序入口
int main(int argc, char *argv[])
{
    // 设置OpenGL格式支持透明
    QSurfaceFormat format;
    format.setAlphaBufferSize(8);
    format.setSamples(4);
    QSurfaceFormat::setDefaultFormat(format);

	// 创建应用程序对象
    QApplication app(argc, argv);

	//// 创建主窗口对象并显示
    MainWidget window;
    window.show();

    // 开始应用程序循环
	qDebug() << "[Qt Operation]Starting application loop...";
    return app.exec();
}
