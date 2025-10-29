#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
    , ui(new Ui::MainWidgetClass())
{
    ui->setupUi(this);
}

MainWidget::~MainWidget()
{
    delete ui;
}

