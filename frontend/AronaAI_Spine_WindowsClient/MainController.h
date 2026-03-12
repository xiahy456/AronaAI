#pragma once

#include "Defines.h"
#include "GlobalVariables.h"

#include <QObject>
#include <QString>
#include <MainWidget.h>
#include <TTSManager.h>

class MainController  : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget& mainWidget, TTSManager& ttsManager);
	~MainController();

	// 执行输出
	void executeOutput(const QString& text);

private:
	MainWidget& m_mainWidget;	// 主界面对象引用
	TTSManager& m_ttsManager;	// 语音合成管理器引用
};

