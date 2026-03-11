#include "opacityanimation.h"

OpacityAnimation::OpacityAnimation(QWidget* widget, double opacity, int duration, QEasingCurve easingCurve) {
    // 构建对象
    this->m_opacityEffect = new QGraphicsOpacityEffect;
    this->m_animation_obj = new QPropertyAnimation(m_opacityEffect, "opacity");
    this->m_widget = widget;
    // 绑定对象
    m_widget->setGraphicsEffect(m_opacityEffect);
    // 初始化frame
    setOpacity(opacity);
    // 初始化动画对象
    m_animation_obj->setDuration(duration);   // 动画持续时间
    m_animation_obj->setEasingCurve(easingCurve);    // 缓入缓出效果
}

void OpacityAnimation::startAnimation(double start_opacity, double goal_opacity) {
    this->m_animation_obj->setStartValue(start_opacity);
    this->m_animation_obj->setEndValue(goal_opacity);
    this->m_animation_obj->start();
}

void OpacityAnimation::setOpacity(double opacity)
{
    this->m_opacityEffect->setOpacity(opacity);
    m_widget->setGraphicsEffect(m_opacityEffect);
}
