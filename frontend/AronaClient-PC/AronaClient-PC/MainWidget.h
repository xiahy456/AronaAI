#pragma once

#include <QtWidgets/QWidget>
#include "ui_MainWidget.h"

QT_BEGIN_NAMESPACE
namespace Ui { class MainWidgetClass; };
QT_END_NAMESPACE

class MainWidget : public QWidget
{
    Q_OBJECT

public:
    MainWidget(QWidget *parent = nullptr);
    ~MainWidget();

private:
    Ui::MainWidgetClass *ui;
};

