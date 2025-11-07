#include "LAppDelegate.hpp"
#include "LAppView.hpp"
#include "LAppPal.hpp"
#include "LAppLive2DManager.hpp"
#include "LAppDefine.hpp"
#include <QTimer>
#include <QMouseEvent>
#include <QCursor>

#include "GLCore.h"

GLCore::GLCore(QWidget* parent)
	: QOpenGLWidget(parent)
{
	// 窗口设置
	//this->setAttribute(Qt::WA_DeleteOnClose);	// 窗口关闭时自动释放内存
	this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
	this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
	this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
	this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
	this->resize(200, 400);

	// Live2D帧率
	QTimer* timer = new QTimer();
	connect(timer, &QTimer::timeout, this, [=]() {
		// 目光跟随鼠标
		QPoint localPos = this->mapFromGlobal(QCursor::pos());
		LAppDelegate::GetInstance()->GetView()->OnTouchesMoved(localPos.x(), localPos.y());
		// 刷新图像
		update();
	});
	timer->start(1.0 / 60 * 1000);	// 60帧刷新率
}

GLCore::~GLCore()
{

}

void GLCore::initializeGL()
{
	LAppDelegate::GetInstance()->Initialize(this);
}

void GLCore::resizeGL(int w, int h)
{
	LAppDelegate::GetInstance()->resize(w, h);
}

void GLCore::paintGL()
{
	LAppDelegate::GetInstance()->update();
}

void GLCore::mousePressEvent(QMouseEvent* event)
{
	LAppDelegate::GetInstance()->GetView()->OnTouchesBegan(event->position().x(), event->position().y());

	// 鼠标事件
	if (event->button() == Qt::LeftButton) {
		this->isLeftBottom = true;
		this->currentPos = event->pos();
	}
	if (event->button() == Qt::RightButton) {
		this->isRightBottom = true;
		this->currentPos = event->pos();
	}
}

void GLCore::mouseMoveEvent(QMouseEvent* event)
{
	LAppDelegate::GetInstance()->GetView()->OnTouchesMoved(event->position().x(), event->position().y());

	// 实现左键拖动窗口逻辑
	if (isLeftBottom) {
		this->move(event->pos() - this->currentPos + this->pos());
	}
}

void GLCore::mouseReleaseEvent(QMouseEvent* event)
{
	LAppDelegate::GetInstance()->GetView()->OnTouchesEnded(event->position().x(), event->position().y());

	// 鼠标事件
	if (event->button() == Qt::LeftButton) {
		this->isLeftBottom = false;
	}
	if (event->button() == Qt::RightButton) {
		this->isRightBottom = false;
	}
}

