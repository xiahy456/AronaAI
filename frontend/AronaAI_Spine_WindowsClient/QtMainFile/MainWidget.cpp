#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
{
    qDebug() << "ദ്ദി˶˃ ᵕ ˂ )✧ [Qt Operation]Loading MainWidget...";  // 调试信息

	// 加载UI界面
    ui.setupUi(this);

    // 100ms时间等待OpenGL初始化，然后加载spine文件并设置初始动画
    QTimer::singleShot(100, [this]() {
        ui.qtSpineManagerWidget->loadSpineFile(
            GET_STRING_FROM_JSON(_global_config, "spine", "atlas_path"),
            GET_STRING_FROM_JSON(_global_config, "spine", "skelOrJson_path")
            );
        ui.qtSpineManagerWidget->setAnimation("Idle_01", 0, true);  // 最基层
        ui.qtSpineManagerWidget->setAnimation("00", 1, true);   // 表情层
        ui.qtSpineManagerWidget->setAnimation("00", 2, true);   // 语言层
        });

    // 初始化相关控件
    m_opacityAnimation_aronaOutputTextBox = new OpacityAnimation(ui.aronaOutputTextBox, 0.0, 250, QEasingCurve::Linear); // 默认气泡文本不透明度为0

    // 窗口设置
    this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    //this->setAttribute(Qt::WA_TransparentForMouseEvents, true); // 设置鼠标穿透点击
    this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
	this->setWindowTitle(GET_STRING_FROM_JSON(_global_dict, "application_data", "main_widget_name"));  // 设置窗口名称

    // 移动窗口
    // 获取主屏幕
    QScreen* screen = QApplication::primaryScreen();
    QRect screenRect = screen->availableGeometry();
    // 计算左下角位置
    int x = screenRect.left();
    int y = screenRect.bottom() - this->height() + 50;
    // 移动窗口
    this->move(x, y);

    // 界面控件设置

    //debug_showText();
}

MainWidget::~MainWidget()
{
}

void MainWidget::showOutputText(const QString& text)
{
    // 更新文本内容
    ui.aronaOutputText->setText(text);
    // 气泡不透明度从0到1
	m_opacityAnimation_aronaOutputTextBox->startAnimation(0.0, 0.7);
}

void MainWidget::hideOutputText()
{
    // 气泡不透明度从1到0
    m_opacityAnimation_aronaOutputTextBox->startAnimation(0.7, 0.0);
}

void MainWidget::setAnimation(const QString& name, int track_idx, bool loop)
{
	ui.qtSpineManagerWidget->setAnimation(name, track_idx, loop);
}

void MainWidget::debug_showText()
{
    // 3秒后显示气泡文本
    QTimer::singleShot(3000, [this]() { showOutputText(GET_STRING_FROM_JSON(_global_dict, "debug", "hello_im_arona")); });
    // 5秒后隐藏气泡文本
    QTimer::singleShot(5000, [this]() { hideOutputText(); });
}

void MainWidget::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::RightButton) {
        m_dragging = true;
        m_dragPosition = event->globalPosition().toPoint() - frameGeometry().topLeft();
        event->accept();
    }
}

void MainWidget::mouseMoveEvent(QMouseEvent* event)
{
    if (m_dragging && (event->buttons() & Qt::RightButton)) {
        move(event->globalPosition().toPoint() - m_dragPosition);
        event->accept();
    }
}

void MainWidget::mouseReleaseEvent(QMouseEvent* event)
{
    if (event->button() == Qt::RightButton) {
        m_dragging = false;
        event->accept();
    }
}
