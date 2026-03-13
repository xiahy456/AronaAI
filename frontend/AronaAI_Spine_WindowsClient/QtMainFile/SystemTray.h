#ifndef SYSTEMTRAY_H
#define SYSTEMTRAY_H

#include <QObject>
#include <QSystemTrayIcon>
#include <QMenu>
#include <QAction>
#include <QCloseEvent>
#include <QApplication>
#include <QMessageBox>

#include "MainWidget.h"

#include "GlobalInclude.h"

class SystemTray : public QObject 
{
	Q_OBJECT

public:
	// 构造函数
	SystemTray(MainWidget* mainWidget, QWidget* settingsWidget);
	// 析构函数
	~SystemTray();

	// 显示主窗口
	void showOrHideMainWidget();
	// 显示设置窗口
	void showOrHideSettingsWidget();
	// 允许操作主菜单
	void ableEdit();
	// 禁止操作主菜单
	void unableEdit();

private:
	MainWidget* m_mainWidget;	// mainWidget主界面对象的引用
	QWidget* m_settingsWidget;	// settingsWidget设置界面对象的引用
	QSystemTrayIcon* m_trayIcon = nullptr;	// 系统托盘图标对象
	QMenu* m_trayIconMenu = nullptr;	// 托盘图标关联的菜单

	QAction* m_operateMainWidget_showOrHide = nullptr;	// 显示/隐藏主界面
	QAction* m_operateSettingsWidget_showOrHide = nullptr;	// 显示/隐藏设置界面
	QAction* m_ableEdit = nullptr;	// 可操作主菜单
	QAction* m_unableEdit = nullptr;	// 不可操作主菜单
	QAction* m_quitAction = nullptr;	// 退出程序
};

#endif // !SYSTEMTRAY_H
