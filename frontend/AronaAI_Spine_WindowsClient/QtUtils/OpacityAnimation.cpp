#include "opacityanimation.h"

OpacityAnimation::OpacityAnimation(QFrame*& frame, double start_opacity, int duration) {
    // 构建对象
    this->opacityEffect = new QGraphicsOpacityEffect;
    this->animation_obj = new QPropertyAnimation(opacityEffect, "opacity");
    // 绑定对象
    frame->setGraphicsEffect(opacityEffect);
    // 初始化frame
    opacityEffect->setOpacity(start_opacity);
    frame->setGraphicsEffect(opacityEffect);
    // 初始化动画对象
    animation_obj->setDuration(duration);   // 动画持续时间
    animation_obj->setEasingCurve(QEasingCurve::InOutQuart);    // 缓入缓出效果
}

void OpacityAnimation::startAnimation(double start_opacity, double goal_opacity) {
    this->animation_obj->setStartValue(start_opacity);
    this->animation_obj->setEndValue(goal_opacity);
    this->animation_obj->start();
}
