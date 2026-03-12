#pragma once

#include "Defines.h"
#include "GlobalVariables.h"

#include <QObject>
#include <QString>
#include <QEventLoop>

#include <MainWidget.h>
#include <TTSManager.h>

class MainController : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget& mainWidget, TTSManager* ttsManager);
	~MainController();

	// 执行输出
	void executeOutput(const QString& text);

private slots:
	void onTTSFinished(const QByteArray& audioData, const QString& mediaType);

private:
	MainWidget& m_mainWidget;	// 主界面对象引用
	TTSManager* m_ttsManager;	// 语音合成管理器指针
	TTSManager::TTSRequestParams ttsRequestParams;	// 语音合成请求参数
	QString m_currentText = "";	// 当前正在处理的文本

};
