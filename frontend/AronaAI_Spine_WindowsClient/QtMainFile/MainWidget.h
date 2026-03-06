#pragma once

#include <QtWidgets/QWidget>
#include "ui_MainWidget.h"

class MainWidget : public QWidget
{
    Q_OBJECT

public:
    MainWidget(QWidget *parent = nullptr);
    ~MainWidget();

private:
    Ui::MainWidgetClass ui;
};

