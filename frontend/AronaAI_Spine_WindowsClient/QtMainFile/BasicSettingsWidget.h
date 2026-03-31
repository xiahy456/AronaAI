#pragma once

#include <ParallelogramWidget.h>
#include <Defines.h>
#include <GlobalInclude.h>
#include <BlueakaFontLoader.h>

#include "ui_BasicSettingsWidget.h"

// Label³õÊ¼»¯ÉèÖÃ
#define LABEL_TEXT_INITIAL(_label, _size, _text, _ss) do { \
	_label->setFont(BlueakaFontLoader::instance()->createFont(_size)); \
	_label->setText(_text); \
	_label->setStyleSheet(_ss); \
} while (0)

class BasicSettingsWidget : public ParallelogramWidget
{
	Q_OBJECT

public:
	BasicSettingsWidget(QWidget *parent = nullptr);
	~BasicSettingsWidget();

private:
	Ui::BasicSettingsWidgetClass ui;
};

