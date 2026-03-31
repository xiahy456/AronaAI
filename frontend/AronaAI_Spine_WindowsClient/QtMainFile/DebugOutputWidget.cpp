#include "DebugOutputWidget.h"

DebugOutputWidget::DebugOutputWidget(QWidget *parent)
	: QWidget(parent)
{
	ui.setupUi(this);
}

DebugOutputWidget::~DebugOutputWidget()
{}

bool DebugOutputWidget::event(QEvent * event)
{
    // 只处理鼠标相关事件
    if (event->type() == QEvent::MouseButtonPress ||
        event->type() == QEvent::MouseButtonRelease ||
        event->type() == QEvent::MouseButtonDblClick ||
        event->type() == QEvent::MouseMove) {

        QMouseEvent* mouseEvent = static_cast<QMouseEvent*>(event);

        // 判断鼠标位置是否在QTextBrowser上
        if (!isMouseOnValidChild(mouseEvent->pos())) {
            // 不在QTextBrowser上，忽略事件，让父控件B处理
            event->ignore();
            return false;  // 返回false表示事件未被处理，继续传播
        }
    }

    // 在QTextBrowser上或非鼠标事件，正常处理
    return QWidget::event(event);
}

bool DebugOutputWidget::isMouseOnValidChild(const QPoint& pos) const
{
    if (!ui.debugOutputText || !ui.debugOutputText->isVisible()) {
        return false;
    }
    // 检查鼠标位置是否在QTextBrowser的几何区域内
    // 注意：pos是相对于WidgetA的坐标
    return ui.debugOutputText->geometry().contains(pos);
}

