#include "MainWidget.h"
#include <QtWidgets/QApplication>
#include <spine/QtSkeletonLoader.h>
#include <spine/QtSpineManager.h>
#include <QDebug>

// 主函数：程序入口
int main(int argc, char *argv[])
{
	// 创建应用程序对象
    QApplication app(argc, argv);

	// 创建主窗口对象并显示
    QtSpineManager* spineManager = new QtSpineManager;
	spineManager->resize(400, 400);
    spineManager->show();
    spineManager->loadSpineFile("D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
    spineManager->setAnimation("Idle_01", 0, true);
    spineManager->setAnimation("18", 1, true);

    //MainWidget window;
    //window.show();

    // 开始应用程序循环
	qDebug() << "Starting application loop...";
    return app.exec();
}
