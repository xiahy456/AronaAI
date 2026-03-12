#pragma once

#include "ui_MainWidget.h"

#include <GlobalInclude.h>

#include <QtWidgets/QWidget>
#include <QVBoxLayout>
#include <QGraphicsOpacityEffect>
#include <QPropertyAnimation>

#include <spine/QtSpineManager.h>

#include <OpacityAnimation.h>

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
    // 设置动画
	void setAnimation(const QString& name, int track_idx, bool loop);

    // Debug-显示文本
	void debug_showText();

protected:
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    Ui::MainWidgetClass ui;

    // 鼠标事件
    bool m_dragging;
    QPoint m_dragPosition;

    // 不透明度动画属性
	OpacityAnimation* m_opacityAnimation_aronaOutputTextBox = nullptr;   // 文本框不透明度动画

};
