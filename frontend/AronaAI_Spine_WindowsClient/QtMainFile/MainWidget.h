#pragma once

#include "ui_MainWidget.h"

#include <QtWidgets/QWidget>
#include <QVBoxLayout>
#include <QGraphicsOpacityEffect>
#include <QPropertyAnimation>

#include <spine/QtSpineManager.h>

class MainWidget : public QWidget
{
    Q_OBJECT

public:
	// 构造函数
    MainWidget(QWidget *parent = nullptr);
	// 析构函数
    ~MainWidget();
	// 显示输出文本并显示气泡
	void showOutputText(const QString& text);
    // 隐藏输出文本并隐藏气泡
	void hideOutputText();
    // 设置控件不透明度
	void setWidgetOpacity(QWidget* widget, QGraphicsOpacityEffect* effect, float opacity);
    // 实现不透明度动画
    void opacityAnimation(QWidget* widget, QGraphicsOpacityEffect* effect,
        float startValue, float endValue, int duration,
        QEasingCurve easingCurve);

protected:
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    Ui::MainWidgetClass ui;

    // 鼠标事件
    bool m_dragging;
    QPoint m_dragPosition;

    // 不透明度属性
    QGraphicsOpacityEffect* m_opacityEffect_textBox = nullptr;

};
