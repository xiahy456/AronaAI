#include "TrayIcon.h"

TrayIcon::TrayIcon(QWidget* parent)
    : QSystemTrayIcon(parent)
    , m_parent(parent)
{
    // 创建图标
    this->createTrayIcon();

    // 创建简单图标
    QPixmap pixmap(16, 16);
    pixmap.fill(Qt::red);
    this->setIcon(QIcon(pixmap));

    // 设置信号与槽连接
    connect(m_showMainWindow_action, &QAction::triggered, this, &TrayIcon::onShowMainWindow);
    connect(m_exitApplication_action, &QAction::triggered, this, &TrayIcon::onExitApplication);
	connect(m_settings_action, &QAction::triggered, this, &TrayIcon::onSettings);

    // 设置ToolTip
    setToolTip("Arona Client");
    // 显示自己
    this->show();
}

TrayIcon::~TrayIcon()
{
    delete m_trayMenu;
}

void TrayIcon::createTrayIcon()
{
    // 实例化右键菜单对象
    m_trayMenu = new QMenu();

    // 添加控件
    m_showMainWindow_action = new QAction(tr("显示主界面"), this);
    m_exitApplication_action = new QAction(tr("退出应用程序"), this);
    m_settings_action = new QAction(tr("设置"), this);

    // 为右键菜单添加图标
    m_trayMenu->addAction(m_showMainWindow_action);
    m_trayMenu->addAction(m_settings_action);
    m_trayMenu->addSeparator(); // 添加分隔线
    m_trayMenu->addAction(m_exitApplication_action);

    setContextMenu(m_trayMenu);
}

void TrayIcon::onShowMainWindow()
{
    if (m_parent) {
        m_parent->setAttribute(Qt::WA_TranslucentBackground);
        //m_parent->setWindowFlags(m_parent->windowFlags() | Qt::FramelessWindowHint);    //无边框
        m_parent->show();
        m_parent->raise();
        m_parent->activateWindow();
    }
}

void TrayIcon::onExitApplication()
{
    qApp->quit();
}

void TrayIcon::onSettings()
{
    
}
