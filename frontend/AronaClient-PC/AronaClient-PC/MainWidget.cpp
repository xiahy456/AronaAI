#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
    , ui(new Ui::MainWidgetClass())
{
    // 设置背景透明
    //this->setAttribute(Qt::WA_TranslucentBackground);
    //this->setWindowFlags(windowFlags() | Qt::FramelessWindowHint);

    // 启动UI
    ui->setupUi(this);

    // 设置窗口名称
    this->setWindowTitle("阿罗娜");

    // 启动最小化托盘菜单
    this->m_trayIcon = new TrayIcon(this);
}

MainWidget::~MainWidget()
{
    delete ui;
}

void MainWidget::closeEvent(QCloseEvent* event)
{
    this->hide();
}
