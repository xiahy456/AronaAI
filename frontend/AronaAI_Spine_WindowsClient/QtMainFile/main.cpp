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

    // 创建QtSpineManager窗口对象并显示
    QtSpineManager* spineManager = new QtSpineManager();
    spineManager->resize(400, 500);
    //spineManager->show();
    QTimer::singleShot(100, [spineManager]() {
        spineManager->loadSpineFile("D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
        spineManager->setAnimation("Idle_01", 0, true);
        spineManager->setAnimation("11", 1, true);
        });
    spineManager->show();
    
    

	//// 创建主窗口对象并显示
 //   MainWidget window;
 //   window.resize(800, 600);
 //   window.show();

    // 开始应用程序循环
	qDebug() << "Starting application loop...";
    return app.exec();
}
