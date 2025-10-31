#pragma once

#include <QtWidgets/QWidget>
#include <QGridLayout>
#include "Macros.h"
#include "ui_MainWidget.h"
#include "GLCore.h"
#include "TrayIcon.h"

QT_BEGIN_NAMESPACE
namespace Ui { class MainWidgetClass; };
QT_END_NAMESPACE

class MainWidget : public QWidget
{
    Q_OBJECT

public:
    MainWidget(QWidget *parent = nullptr);
    ~MainWidget();

protected:
    void closeEvent(QCloseEvent* event) override;

private:
    Ui::MainWidgetClass *ui;
    // GLCore窗口
    //GLCore* m_gLCore;
    // 托盘图标
    TrayIcon* m_trayIcon;
};

