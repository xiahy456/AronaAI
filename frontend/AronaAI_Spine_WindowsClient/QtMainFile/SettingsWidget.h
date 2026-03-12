#pragma once

#include <QWidget>
#include <QCloseEvent>

#include "GlobalInclude.h"

#include "ui_SettingsWidget.h"

class SettingsWidget : public QWidget
{
	Q_OBJECT

public:
	SettingsWidget(QWidget *parent = nullptr);
	~SettingsWidget();

protected:
	void closeEvent(QCloseEvent* event) override;

private:
	Ui::SettingsWidgetClass ui;
};

