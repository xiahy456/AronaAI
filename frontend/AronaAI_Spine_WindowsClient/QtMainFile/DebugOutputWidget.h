#pragma once

#ifndef DEBUGOUTPUTWIDGET_H
#define DEBUGOUTPUTWIDGET_H

#include <QWidget>
#include <QMouseEvent>

#include "ui_DebugOutputWidget.h"

class DebugOutputWidget : public QWidget
{
	Q_OBJECT

public:
	DebugOutputWidget(QWidget *parent = nullptr);
	~DebugOutputWidget();

protected:
	bool event(QEvent* event) override;

private:
	Ui::DebugOutputWidgetClass ui;

	bool isMouseOnValidChild(const QPoint& pos) const;
};

#endif // !DEBUGOUTPUTWIDGET_H
