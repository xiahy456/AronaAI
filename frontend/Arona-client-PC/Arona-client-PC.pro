QT       += core gui
QT       += opengl
QT       += openglwidgets

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

CONFIG += c++17

# 忽略默认库冲突
QMAKE_LFLAGS_WINDOWS += /NODEFAULTLIB:MSVCRT
QMAKE_LFLAGS_WINDOWS += /NODEFAULTLIB:LIBCMT

# 设置调试版本与发布版本的运行库
CONFIG(debug, debug|release) {
    # 调试模式使用 MDd
    QMAKE_CXXFLAGS_DEBUG -= -MTd
    QMAKE_CXXFLAGS_DEBUG += -MDd
} else {
    # 发布模式使用 MD
    QMAKE_CXXFLAGS_RELEASE -= -MT
    QMAKE_CXXFLAGS_RELEASE += -MD
}

INCLUDEPATH += $$PWD/../Thirdparty/Core/include
INCLUDEPATH += $$PWD/../Thirdparty/Framework/src
INCLUDEPATH += $$PWD/../Thirdparty/glew/include
INCLUDEPATH += $$PWD/../Thirdparty/glfw/include
INCLUDEPATH += $$PWD/../Thirdparty/stb
#INCLUDEPATH += $$PWD/Resources

# 库文件配置
debug {
    LIBS += -L$$PWD/../Lib/Debug
    LIBS += -lFramework
    LIBS += -llibglew32d
    LIBS += -lglfw3
    LIBS += -lLive2DCubismCore_MTd
}

release {
    LIBS += -L$$PWD/../Lib/Release
    LIBS += -lFramework
    LIBS += -llibglew32
    LIBS += -lglfw3
    LIBS += -lLive2DCubismCore_MT
}

# 定义 GLEW_STATIC 如果使用静态库
DEFINES += GLEW_STATIC

DEFINES += GLFW_DLL

# OpenGL 库
LIBS += -lopengl32 -lglu32

SOURCES += \
    GLCore.cpp \
    LAppDefine.cpp \
    LAppDelegate.cpp \
    LAppLive2DManager.cpp \
    LAppModel.cpp \
    LAppPal.cpp \
    LAppSprite.cpp \
    LAppSpriteShader.cpp \
    LAppTextureManager.cpp \
    LAppView.cpp \
    MouseActionManager.cpp \
    main.cpp \
    mainwidget.cpp

HEADERS += \
    GLCore.h \
    LAppDefine.hpp \
    LAppDelegate.hpp \
    LAppLive2DManager.hpp \
    LAppModel.hpp \
    LAppPal.hpp \
    LAppSprite.hpp \
    LAppSpriteShader.hpp \
    LAppTextureManager.hpp \
    LAppView.hpp \
    Macros.h \
    MouseActionManager.hpp \
    mainwidget.h \
    stdafx.h

# DirectX 库
LIBS += -ld3d9
LIBS += -ld3dcompiler
LIBS += -ldxgi
LIBS += -ldxguid

# Vulkan 库
#LIBS += -lvulkan-1

FORMS += \
    mainwidget.ui

TRANSLATIONS += \
    Arona-client-PC_zh_CN.ts
CONFIG += lrelease
CONFIG += embed_translations

DEFINES += CSM_TARGET_WIN_GL

# Default rules for deployment.
qnx: target.path = /tmp/$${TARGET}/bin
else: unix:!android: target.path = /opt/$${TARGET}/bin
!isEmpty(target.path): INSTALLS += target
