/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

	  https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

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
	void onSwitchAudioInput();			// 切换语音输入设备的槽函数
	void onSwitchMouseTransparent();	// 切换鼠标穿透的槽函数

private:
	MainController* m_mainController = nullptr;	// MainController类对象引用
	QHotkey* m_switchAudioInput = nullptr;		// 激活语音输入热键对象
	QHotkey* m_switchMouseTransparent = nullptr;	// 切换鼠标穿透热键对象
	bool m_switchAudioInputEnabled = false;		// 是否启用切换语音输入热键的标志

};
