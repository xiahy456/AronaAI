#ifndef OPACITYANIMATION_H
#define OPACITYANIMATION_H

#include <QFrame>
#include <QGraphicsOpacityEffect>
#include <QPropertyAnimation>

class OpacityAnimation
{
public:
    OpacityAnimation(QFrame*& frame, double start_opacity, int duration);

    // 初始化不透明度，初始化动画
    void startAnimation(double start_opacity, double goal_opacity);

    // 不透明度效果对象
    QGraphicsOpacityEffect* opacityEffect;
    // 动画对象
    QPropertyAnimation* animation_obj;
};

#endif // OPACITYANIMATION_H
