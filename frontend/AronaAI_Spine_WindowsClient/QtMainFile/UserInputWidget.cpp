#include "UserInputWidget.h"

#include <QApplication>
#include <QScreen>

UserInputWidget::UserInputWidget(QWidget *parent)
	: QWidget(parent)
{
	ui.setupUi(this);

    // 窗口设置
    this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
    this->setAutoFillBackground(false);   // 禁用自动填充背景
    this->setWindowTitle(GET_STRING_FROM_JSON(_global_dict, "application_data", "user_input_widget_name"));  // 设置窗口名称

    // 设置窗口大小并居中靠下放置
    this->resize(940 * WIDGET_ZOOM, 25 * WIDGET_ZOOM);
    QScreen* screen = QApplication::primaryScreen();
    QRect screenRect = screen->availableGeometry();
    this->move(screenRect.left() + (screenRect.width() - this->width()) / 2,
        screenRect.bottom() - this->height() - 80 * WIDGET_ZOOM);
    m_normalGeometry = this->geometry();

	// 输入背景
    ui.inputBGWidget->move(0 * WIDGET_ZOOM, 0 * WIDGET_ZOOM);
    ui.inputBGWidget->setFixedSize(940 * WIDGET_ZOOM, 25 * WIDGET_ZOOM);
    ui.inputBGWidget->setFillBackground(true);
    ui.inputBGWidget->setBackgroundImage(GET_STRING_FROM_JSON(_global_config, "settings", "top_information_path"));

    // 输入框
    ui.inputLineEdit->move(0 * WIDGET_ZOOM, 0 * WIDGET_ZOOM);
    ui.inputLineEdit->resize(940 * WIDGET_ZOOM, 25 * WIDGET_ZOOM);
    ui.inputLineEdit->setFont(BlueakaFontLoader::instance()->createFont(11 * WIDGET_ZOOM));
    ui.inputLineEdit->setStyleSheet(
        "color: rgb(44, 69, 99);"
        "background: transparent;"
        "border: none;"
    );
    ui.inputLineEdit->clear();
    ui.inputLineEdit->setPlaceholderText(GET_STRING_FROM_JSON(_global_dict, "application_data", "user_input_widget_placeholder"));
    ui.inputLineEdit->installEventFilter(this);

    connect(ui.inputLineEdit, &QLineEdit::returnPressed, this, &UserInputWidget::onReturnPressed);
}

UserInputWidget::~UserInputWidget()
{}

void UserInputWidget::showForInput()
{
    if (m_bounceAnimation) {
        QSequentialAnimationGroup* anim = m_bounceAnimation;
        m_bounceAnimation = nullptr;
        anim->disconnect(this);
        anim->stop(); // DeleteWhenStopped
    }
    m_isSubmitting = false;
    this->setGeometry(m_normalGeometry);
    syncChildrenGeometry();
    ui.inputLineEdit->clear();
    this->show();
    this->raise();
    this->activateWindow();
    ui.inputLineEdit->setFocus(Qt::OtherFocusReason);
}

void UserInputWidget::onReturnPressed()
{
    if (m_isSubmitting) {
        return;
    }

    const QString text = ui.inputLineEdit->text().trimmed();
    if (text.isEmpty()) {
        this->hide();
        return;
    }

    // 发送信号必须早于或等于弹跳动画开始
    emit textSubmitted(text);
    playSubmitBounceAnimation();
}

void UserInputWidget::playSubmitBounceAnimation()
{
    m_isSubmitting = true;
    m_normalGeometry = this->geometry();

    const QRect normal = m_normalGeometry;
    const int shrinkW = qMax(1, qRound(normal.width() * 0.92));
    const int shrinkH = qMax(1, qRound(normal.height() * 0.70));
    const QRect shrunk(
        normal.center().x() - shrinkW / 2,
        normal.center().y() - shrinkH / 2,
        shrinkW,
        shrinkH
    );

    if (m_bounceAnimation) {
        QSequentialAnimationGroup* anim = m_bounceAnimation;
        m_bounceAnimation = nullptr;
        anim->stop(); // DeleteWhenStopped
    }

    auto* shrinkAnim = new QPropertyAnimation(this, "geometry");
    shrinkAnim->setDuration(150);
    shrinkAnim->setStartValue(normal);
    shrinkAnim->setEndValue(shrunk);
    shrinkAnim->setEasingCurve(QEasingCurve::InQuad);

    auto* restoreAnim = new QPropertyAnimation(this, "geometry");
    restoreAnim->setDuration(350);
    restoreAnim->setStartValue(shrunk);
    restoreAnim->setEndValue(normal);
    restoreAnim->setEasingCurve(QEasingCurve::OutBounce);

    m_bounceAnimation = new QSequentialAnimationGroup(this);
    m_bounceAnimation->addAnimation(shrinkAnim);
    m_bounceAnimation->addAnimation(restoreAnim);

    connect(m_bounceAnimation, &QSequentialAnimationGroup::finished, this, [this]() {
        m_bounceAnimation = nullptr;
        m_isSubmitting = false;
        this->setGeometry(m_normalGeometry);
        syncChildrenGeometry();
        this->hide();
    });

    m_bounceAnimation->start(QAbstractAnimation::DeleteWhenStopped);
}

void UserInputWidget::syncChildrenGeometry()
{
    ui.inputBGWidget->move(0, 0);
    ui.inputBGWidget->setFixedSize(this->size());
    ui.inputLineEdit->move(0, 0);
    ui.inputLineEdit->resize(this->size());
}

void UserInputWidget::stopBounceAndHide()
{
    if (m_bounceAnimation) {
        QSequentialAnimationGroup* anim = m_bounceAnimation;
        m_bounceAnimation = nullptr;
        anim->disconnect(this);
        anim->stop(); // DeleteWhenStopped
    }
    m_isSubmitting = false;
    this->setGeometry(m_normalGeometry);
    syncChildrenGeometry();
    this->hide();
}

void UserInputWidget::keyPressEvent(QKeyEvent* event)
{
    if (event->key() == Qt::Key_Escape) {
        stopBounceAndHide();
        event->accept();
        return;
    }
    QWidget::keyPressEvent(event);
}

bool UserInputWidget::eventFilter(QObject* watched, QEvent* event)
{
    if (watched == ui.inputLineEdit && event->type() == QEvent::KeyPress) {
        QKeyEvent* keyEvent = static_cast<QKeyEvent*>(event);
        if (keyEvent->key() == Qt::Key_Escape) {
            stopBounceAndHide();
            return true;
        }
    }
    return QWidget::eventFilter(watched, event);
}

void UserInputWidget::changeEvent(QEvent* event)
{
    // 提交动画期间忽略失焦关闭，避免发送过程中被提前隐藏
    if (event->type() == QEvent::WindowDeactivate && this->isVisible() && !m_isSubmitting) {
        this->hide();
    }
    QWidget::changeEvent(event);
}

void UserInputWidget::resizeEvent(QResizeEvent* event)
{
    QWidget::resizeEvent(event);
    syncChildrenGeometry();
}
