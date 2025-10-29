#include "stdafx.h"
#include "Macros.h"
#include "GLCore.h"

int main(int argc, char *argv[])
{
    // 创建应用程序对象
    QApplication app_obj(argc, argv);

    // 翻译器初始化
    TRANSLATOR_INITIALIZE(app_obj);

    // 启动主界面
    GLCore w;
    w.show();

    // 进入交互主循环
    return app_obj.exec();
}
