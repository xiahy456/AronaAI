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
    this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    //this->setAttribute(Qt::WA_TransparentForMouseEvents, true); // 设置鼠标穿透点击
    this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    //this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    //this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
    this->setAutoFillBackground(false);   // 禁用自动填充背景
    this->setWindowTitle(GET_STRING_FROM_JSON(_global_dict, "application_data", "settings_widget_name"));  // 设置窗口名称

    // 设置窗口大小
    this->resize(780 * WIDGET_ZOOM, 400 * WIDGET_ZOOM);

    // 控件设置
    // 界面切换按钮
    WIDGET_SWITCH_SETTING(ui.basicSettingsButton, 0)
    WIDGET_SWITCH_SETTING(ui.aronaLMSettingsButton, 1)
    WIDGET_SWITCH_SETTING(ui.spineSettingsButton, 2)
    WIDGET_SWITCH_SETTING(ui.gptSOVITSSettingsButton, 3)
    WIDGET_SWITCH_SETTING(ui.debugOutputButton, 4)
    WIDGET_SWITCH_SETTING(ui.aboutDeveloperButton, 5)

    // 上方信息栏
    ui.topInformationWidget->move((widgetSwitchButton_start_x + 40*0.5574 - 2) * WIDGET_ZOOM, (widgetSwitchButton_start_y - 30) * WIDGET_ZOOM);
    ui.topInformationWidget->setFixedSize(640, 20);

    // 主界面背景
    ui.mainBGWidget->move(80 * WIDGET_ZOOM, 20 * WIDGET_ZOOM);
    ui.mainBGWidget->setFixedSize(684 * WIDGET_ZOOM, 380 * WIDGET_ZOOM);
    ui.mainBGWidget->setBackgroundImage(GET_STRING_FROM_JSON(_global_config, "settings", "settings_bg_path"));
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

void SettingsWidget::mousePressEvent(QMouseEvent* event)
{
    // 检查是否点击在可拖动的控件上
    if (ui.topInformationWidget && ui.topInformationWidget->geometry().contains(event->pos()))
    {
        m_isDragging = true;
        m_dragPosition = event->globalPosition() - frameGeometry().topLeft();
        event->accept();
    }
    else
    {
        QWidget::mousePressEvent(event);
    }
}

void SettingsWidget::mouseMoveEvent(QMouseEvent* event)
{
    if (m_isDragging && (event->buttons() & Qt::LeftButton))
    {
        move((event->globalPosition() - m_dragPosition).toPoint());
        event->accept();
    }
    else
    {
        QWidget::mouseMoveEvent(event);
    }
}

void SettingsWidget::mouseReleaseEvent(QMouseEvent* event)
{
    if (m_isDragging)
    {
        m_isDragging = false;
        event->accept();
    }
    else
    {
        QWidget::mouseReleaseEvent(event);
    }
}
