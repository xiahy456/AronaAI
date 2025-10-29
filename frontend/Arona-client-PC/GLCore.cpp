#include "LAppDelegate.hpp"
#include "LAppView.hpp"
#include "LAppPal.hpp"
#include "LAppLive2DManager.hpp"
#include "LAppDefine.hpp"

#include "GLCore.h"

GLCore::GLCore(QWidget* parent)
    : QOpenGLWidget(parent)
{

}

GLCore::~GLCore()
{

}

void GLCore::initializeGL()
{
    LAppDelegate::GetInstance()->Initialize(this);
}

void GLCore::paintGL()
{
    LAppDelegate::GetInstance()->update();
}


void GLCore::resizeGL(int w, int h)
{
    LAppDelegate::GetInstance()->resize(w, h);
}
