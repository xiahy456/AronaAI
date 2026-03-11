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

private:
	QWidget& m_mainWidget;	// mainWidget主界面对象的引用
	QWidget& m_settingsWidget;	// settingsWidget设置界面对象的引用
	QSystemTrayIcon* m_trayIcon;	// 系统托盘图标对象
	QMenu* m_trayIconMenu;	// 托盘图标关联的菜单
	QAction* m_operateMainWidget_hide;	// 隐藏主界面
	QAction* m_operateMainWidget_show;	// 显示主界面
	QAction* m_operateSettingsWidget_hide;	// 隐藏设置界面
	QAction* m_operateSettingsWidget_show;	// 显示设置界面
	QAction* m_quitAction;	// 退出动作
};

#endif // !SYSTEMTRAY_H
