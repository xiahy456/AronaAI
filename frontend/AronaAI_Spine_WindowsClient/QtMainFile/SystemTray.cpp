#include <SystemTray.h>

SystemTray::SystemTray(MainWidget* mainWidget, QWidget* settingsWidget)
    : m_mainWidget(mainWidget)
	, m_settingsWidget(settingsWidget)
{
    // 检查系统是否支持托盘图标
    if (!QSystemTrayIcon::isSystemTrayAvailable()) {
        QMessageBox::critical(nullptr, GET_STRING_FROM_JSON(_global_dict, "application_data", "system_tray"), GET_STRING_FROM_JSON(_global_dict, "application_data", "system_tray_not_support"));
        // 可以选择退出或继续但不显示托盘
        return;
    }

    // 创建动作 (Actions)
    m_operateMainWidget_showOrHide = new QAction(GET_STRING_FROM_JSON(_global_dict, "application_data", "showOrHide_main_widget"));
    m_operateSettingsWidget_showOrHide = new QAction(GET_STRING_FROM_JSON(_global_dict, "application_data", "showOrHide_settings_widget"));
    m_ableEdit = new QAction(GET_STRING_FROM_JSON(_global_dict, "application_data", "able_edit"));
    m_unableEdit = new QAction(GET_STRING_FROM_JSON(_global_dict, "application_data", "unable_edit"));
    m_quitAction = new QAction(GET_STRING_FROM_JSON(_global_dict, "application_data", "quit"));

    // 连接动作的信号到对应的槽函数
    connect(m_operateMainWidget_showOrHide, &QAction::triggered, this, &SystemTray::showOrHideMainWidget);
    connect(m_operateSettingsWidget_showOrHide, &QAction::triggered, this, &SystemTray::showOrHideSettingsWidget);
    connect(m_ableEdit, &QAction::triggered, this, &SystemTray::ableEdit);
    connect(m_unableEdit, &QAction::triggered, this, &SystemTray::unableEdit);
    connect(m_quitAction, &QAction::triggered, qApp, &QApplication::quit);

    // 创建托盘图标和菜单
    m_trayIconMenu = new QMenu();
    m_trayIconMenu->addAction(m_operateMainWidget_showOrHide);
    m_trayIconMenu->addAction(m_operateSettingsWidget_showOrHide);
    m_trayIconMenu->addAction(m_ableEdit);
    m_trayIconMenu->addAction(m_unableEdit);
    m_trayIconMenu->addSeparator(); // 添加分隔线
    m_trayIconMenu->addAction(m_quitAction);

    // 创建托盘图标
    m_trayIcon = new QSystemTrayIcon(this);
    m_trayIcon->setIcon(QIcon(GET_STRING_FROM_JSON(_global_config, "settings", "icon_path")));  // 请替换为你的图标资源路径
    m_trayIcon->setToolTip(GET_STRING_FROM_JSON(_global_dict, "application_data", "application_name")); // 鼠标悬停时的提示

    // 将菜单设置给托盘图标（右键菜单）
    m_trayIcon->setContextMenu(m_trayIconMenu);

    // 最后，显示托盘图标
    m_trayIcon->show();

}

SystemTray::~SystemTray()
{
}

void SystemTray::showOrHideMainWidget()
{
    if (m_mainWidget->isVisible()) m_mainWidget->hide();
    else m_mainWidget->show();
}

void SystemTray::showOrHideSettingsWidget()
{
	if (m_settingsWidget->isVisible()) m_settingsWidget->hide();
    else m_settingsWidget->show();
}

void SystemTray::ableEdit()
{
    m_mainWidget->setMouseAble(true);
}

void SystemTray::unableEdit()
{
    m_mainWidget->setMouseAble(false);
}
