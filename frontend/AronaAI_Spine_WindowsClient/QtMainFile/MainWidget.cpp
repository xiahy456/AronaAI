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
        ui.qtSpineManagerWidget->setAnimation("Idle_01", 0, true);
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

    // 初始动画启动
    // 2秒后显示气泡文本
    QTimer::singleShot(2000, [this]() { showOutputText(GET_STRING_FROM_JSON(_global_dict, "formed_text", "connected_to_os_operator")); });
    // 4秒后隐藏气泡文本
    QTimer::singleShot(5000, [this]() { hideOutputText(); });

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

void MainWidget::setWidgetOpacity(QWidget* widget, QGraphicsOpacityEffect* effect, float opacity)
{
	if (!widget) return;
    effect->setOpacity(opacity);
    widget->setGraphicsEffect(effect);
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

void MainWidget::opacityAnimation(QWidget* widget, QGraphicsOpacityEffect* effect,
    float startValue, float endValue, int duration,
    QEasingCurve easingCurve)
{
    if (!effect) return;

    // 停止可能正在进行的动画
    effect->setOpacity(startValue);

    QPropertyAnimation* animation = new QPropertyAnimation(effect, "opacity");
    animation->setDuration(duration);
    animation->setStartValue(startValue);
    animation->setEndValue(endValue);
    animation->setEasingCurve(easingCurve);
    animation->start(QAbstractAnimation::DeleteWhenStopped);
}