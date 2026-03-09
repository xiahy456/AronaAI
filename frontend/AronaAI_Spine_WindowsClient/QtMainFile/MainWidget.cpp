#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
{
    ui.setupUi(this);

    QtSpineManager* spineWidget = new QtSpineManager(this);
    spineWidget->loadSpineFile("D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
    spineWidget->setAnimation("Idle_01", true);
}

MainWidget::~MainWidget()
{
}

