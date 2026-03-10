#include "MainWidget.h"

MainWidget::MainWidget(QWidget *parent)
    : QWidget(parent)
{
    qDebug() << "[Qt Operation]Loading MainWidget...";  // 调试信息
    ui.setupUi(this);

	// 100ms时间等待OpenGL初始化，然后加载spine文件并设置初始动画
    QTimer::singleShot(100, [this]() {
        ui.qtSpineManagerWidget->loadSpineFile(
            "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/Arona01.atlas", 
            "D:/Code/projects/Arona/arona-ai/frontend/AronaAI_Spine_WindowsClient/AronaSpineAssets/arona_spr.json");
        ui.qtSpineManagerWidget->setAnimation("Idle_01", 0, true);
        });

    // 窗口设置
    this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    //this->setAttribute(Qt::WA_TransparentForMouseEvents, true); // 设置鼠标穿透点击
    this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    //this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标

    // 初始化相关控件
    m_opacityEffect_textBox = new QGraphicsOpacityEffect(this);

    // 界面控件设置
	// 默认气泡文本不透明度为0，后续根据需要显示
	setWidgetOpacity(ui.aronaOutputTextBox, m_opacityEffect_textBox, 0.0);

	// 测试代码：3秒后显示气泡文本，5秒后隐藏气泡文本
    QTimer::singleShot(3000, [this]() { showOutputText("Hello, I'm Arona!"); });
	QTimer::singleShot(8000, [this]() { hideOutputText(); });
}

MainWidget::~MainWidget()
{
}

void MainWidget::showOutputText(const QString& text)
{
    // 显示气泡
    ui.aronaOutputTextBox->show();
    // 更新文本内容
    ui.aronaOutputText->setText(text);
    // 气泡不透明度从0到1
    opacityAnimation(ui.aronaOutputTextBox, m_opacityEffect_textBox, 0.0, 1.0, 250, QEasingCurve::Linear);
}

void MainWidget::hideOutputText()
{
    // 气泡不透明度从1到0
    opacityAnimation(ui.aronaOutputTextBox, m_opacityEffect_textBox, 1.0, 0.0, 250, QEasingCurve::Linear);
}

void MainWidget::setWidgetOpacity(QWidget* widget, QGraphicsOpacityEffect* effect, float opacity)
{
	if (!widget) return;
    effect->setOpacity(opacity);
    widget->setGraphicsEffect(effect);
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
