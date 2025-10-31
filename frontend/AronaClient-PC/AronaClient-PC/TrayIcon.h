#pragma once
#include <QSystemTrayIcon>
#include <QWidget>
#include <QApplication>
#include <QMenu>
#include <QAction>

class TrayIcon : public QSystemTrayIcon
{
	Q_OBJECT
public:
	explicit TrayIcon(QWidget* parent);
	~TrayIcon();

private slots:
	void onShowMainWindow();
	void onExitApplication();
	void onSettings();

private:
	void createTrayIcon();

	QWidget* m_parent;
	QMenu* m_trayMenu;
	QAction* m_showMainWindow_action;
	QAction* m_exitApplication_action;
	QAction* m_settings_action;
};