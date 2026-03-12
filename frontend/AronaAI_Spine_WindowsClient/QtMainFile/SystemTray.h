#ifndef SYSTEMTRAY_H
#define SYSTEMTRAY_H

#include <QObject>
#include <QSystemTrayIcon>
#include <QMenu>
#include <QAction>
#include <QCloseEvent>
#include <QApplication>
#include <QMessageBox>

#include "GlobalInclude.h"

class SystemTray : public QObject 
{
	Q_OBJECT

public:
	// 构造函数
	SystemTray(QWidget& mainWidget, QWidget& settingsWidget);
	// 析构函数
	~SystemTray();

	// 显示主窗口
	void showOrHideMainWidget();
	// 显示设置窗口
	void showOrHideSettingsWidget();

private:
	QWidget& m_mainWidget;	// mainWidget主界面对象的引用
	QWidget& m_settingsWidget;	// settingsWidget设置界面对象的引用
	bool m_mainWidgetIsVisible = true;	// 主界面是否可见的标志
	bool m_settingsWidgetIsVisible = false;	// 设置界面是否可见的标志
	QSystemTrayIcon* m_trayIcon;	// 系统托盘图标对象
	QMenu* m_trayIconMenu;	// 托盘图标关联的菜单
	QAction* m_operateMainWidget_showOrHide;	// 显示/隐藏主界面
	QAction* m_operateSettingsWidget_showOrHide;	// 显示/隐藏设置界面
	QAction* m_quitAction;	// 退出动作
};

#endif // !SYSTEMTRAY_H
