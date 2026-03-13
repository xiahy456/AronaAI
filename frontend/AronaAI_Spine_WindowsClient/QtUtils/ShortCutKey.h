#pragma once

#include <Defines.h>
#include <GlobalVariables.h>
#include "MainController.h"

#include <QObject>
#include <QHotKey>
#include <QKeySequence>
#include <QApplication>

class ShortCutKey  : public QObject
{
	Q_OBJECT

public:
	ShortCutKey(MainController* mainController);
	~ShortCutKey();

private slots:
	void onSwitchAudioInput();	// 切换语音输入设备的槽函数

private:
	MainController* m_mainController = nullptr;	// MainController类对象引用
	QHotkey* m_switchAudioInput = nullptr;	// 激活语音输入热键对象
	bool m_switchAudioInputEnabled = false;	// 是否启用切换语音输入热键的标志

};

