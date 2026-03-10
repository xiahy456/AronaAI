#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
{
    qDebug() << "[Qt Operation]Loading MainWidget...";  // 调试信息
    ui.setupUi(this);

    //ui.qtSpineManagerWidget->resize(400, 500);
    //QTimer::singleShot(100, [this]() {
    //    ui.qtSpineManagerWidget->loadSpineFile("D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
    //    ui.qtSpineManagerWidget->setAnimation("Idle_01", 0, true);
    //    ui.qtSpineManagerWidget->setAnimation("11", 1, true);
    //    });


    // 设置窗口透明
    this->setAttribute(Qt::WA_TranslucentBackground);
    setStyleSheet("background:transparent;");

    // 创建QtSpineManager窗口对象并显示
    QtSpineManager* spineManager = new QtSpineManager();
    //spineManager->resize(400, 500);
    QTimer::singleShot(100, [spineManager]() {
        spineManager->loadSpineFile("D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
        spineManager->setAnimation("Idle_01", 0, true);
        spineManager->setAnimation("11", 1, true);
        });
    spineManager->show();
    // 设置spineManager控件的样式
    spineManager->setStyleSheet("background:transparent;");
    spineManager->setAutoFillBackground(false);
    // 创建布局管理器 (这里使用垂直布局)
    QVBoxLayout* layout = new QVBoxLayout;
    layout->addWidget(spineManager);
    // 将布局设置给主窗口
    this->setLayout(layout);
}

MainWidget::~MainWidget()
{
}

