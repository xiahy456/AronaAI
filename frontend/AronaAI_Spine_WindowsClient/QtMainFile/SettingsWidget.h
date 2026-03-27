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

#include <QWidget>
#include <QCloseEvent>

#include "GlobalInclude.h"

#include "ui_SettingsWidget.h"

// 按键排布位移
#define STEP_POSITION_POINT(_start_x, _start_y, _gap, _step) (_start_x - _gap*_step*0.5773) * WIDGET_ZOOM, (_start_y + _gap*_step) * WIDGET_ZOOM

// 界面切换按钮设置
#define WIDGET_SWITCH_SETTING(button, _cur_step) do { \
	button->move(STEP_POSITION_POINT(widgetSwitchButton_start_x, widgetSwitchButton_start_y, widgetSwitchButton_gap, _cur_step)); \
	button->setFixedSize(widgetSwitchButton_size_x * WIDGET_ZOOM, widgetSwitchButton_size_y * WIDGET_ZOOM); \
	button->setBackgroundImage(GET_STRING_FROM_JSON(_global_config, "settings", "push_button_path")); \
	button->setImageScaleMode(Qt::IgnoreAspectRatio); \
} while (0) \

class SettingsWidget : public QWidget
{
	Q_OBJECT

public:
	SettingsWidget(QWidget *parent = nullptr);
	~SettingsWidget();

protected:
	void closeEvent(QCloseEvent* event) override;
	void mousePressEvent(QMouseEvent* event) override;
	void mouseMoveEvent(QMouseEvent* event) override;
	void mouseReleaseEvent(QMouseEvent* event) override;
	
private slots:
	void onCloseButtonClicked();           // CloseButton被按了 

private:
	// 界面切换按钮实现函数

	Ui::SettingsWidgetClass ui;

	// 界面切换按钮
	int widgetSwitchButton_start_x = 115;	// 最上方的控件x坐标
	int widgetSwitchButton_start_y = 40;	// 最上方的控件y坐标
	int widgetSwitchButton_gap = 40;	// y坐标高度差
	int widgetSwitchButton_size_x = 160;	// 按钮x尺寸
	int widgetSwitchButton_size_y = 30;	// 按钮y尺寸

	// 鼠标拖动
	QPointF m_dragPosition;  // 记录拖动起始位置
	bool m_isDragging;       // 是否正在拖动
};

