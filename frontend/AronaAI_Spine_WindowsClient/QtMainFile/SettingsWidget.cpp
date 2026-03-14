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

#include "SettingsWidget.h"

SettingsWidget::SettingsWidget(QWidget *parent)
	: QWidget(parent)
{
    // 加载UI界面
	ui.setupUi(this);
    
    // 窗口设置
    //this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    //this->setAttribute(Qt::WA_TransparentForMouseEvents, true); // 设置鼠标穿透点击
    //this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    //this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    //this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
    this->setAutoFillBackground(false);   // 禁用自动填充背景
    this->setWindowTitle(GET_STRING_FROM_JSON(_global_dict, "application_data", "settings_widget_name"));  // 设置窗口名称
}

SettingsWidget::~SettingsWidget()
{

}

void SettingsWidget::closeEvent(QCloseEvent * event)
{
    // 忽略关闭事件，改为隐藏窗口
    event->ignore();
    this->hide();
}

