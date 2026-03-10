#pragma once

#include "ui_MainWidget.h"

#include <QtWidgets/QWidget>
#include <QVBoxLayout>

#include <spine/QtSpineManager.h>

class MainWidget : public QWidget
{
    Q_OBJECT

public:
    MainWidget(QWidget *parent = nullptr);
    ~MainWidget();

private:
    Ui::MainWidgetClass ui;
};

