#include <SystemTray.h>

SystemTray::SystemTray(QWidget& mainWidget, QWidget& settingsWidget) :
	m_mainWidget(mainWidget),
	m_settingsWidget(settingsWidget)
{
    // 检查系统是否支持托盘图标 (推荐)
    if (!QSystemTrayIcon::isSystemTrayAvailable()) {
        QMessageBox::critical(nullptr, "系统托盘", "您的系统不支持系统托盘。");
        // 可以选择退出或继续但不显示托盘
    }

    // 创建动作 (Actions)
    m_operateMainWidget_hide = new QAction("隐藏主界面");
    m_operateMainWidget_show = new QAction("显示主界面");
    m_operateSettingsWidget_hide = new QAction("隐藏设置界面");
    m_operateSettingsWidget_show = new QAction("显示设置界面");
    m_quitAction = new QAction("退出");

    // 连接动作的信号到对应的槽函数
    connect(m_operateMainWidget_hide, &QAction::triggered, &m_mainWidget, &QWidget::showMinimized);
    connect(m_operateMainWidget_show, &QAction::triggered, &m_mainWidget, &QWidget::showNormal);
    connect(m_operateSettingsWidget_hide, &QAction::triggered, &m_settingsWidget, &QWidget::showMinimized);
    connect(m_operateSettingsWidget_show, &QAction::triggered, &m_settingsWidget, &QWidget::showNormal);
    connect(m_quitAction, &QAction::triggered, qApp, &QApplication::quit);

    // 创建托盘图标和菜单
    m_trayIconMenu = new QMenu();
    m_trayIconMenu->addAction(m_operateMainWidget_show);
    m_trayIconMenu->addAction(m_operateMainWidget_hide);
    m_trayIconMenu->addAction(m_operateSettingsWidget_show);
    m_trayIconMenu->addAction(m_operateSettingsWidget_hide);
    m_trayIconMenu->addSeparator(); // 添加分隔线
    m_trayIconMenu->addAction(m_quitAction);

    // 创建托盘图标
    m_trayIcon = new QSystemTrayIcon(this);
    m_trayIcon->setIcon(QIcon(GET_STRING_FROM_JSON(_global_config, "settings", "icon_path"))); // 请替换为你的图标资源路径
    m_trayIcon->setToolTip("阿罗娜AI"); // 鼠标悬停时的提示

    // 将菜单设置给托盘图标（右键菜单）
    m_trayIcon->setContextMenu(m_trayIconMenu);

    // 最后，显示托盘图标
    m_trayIcon->show();

}

SystemTray::~SystemTray()
{
}
