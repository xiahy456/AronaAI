#ifndef OPACITYANIMATION_H
#define OPACITYANIMATION_H

#include <QFrame>
#include <QGraphicsOpacityEffect>
#include <QPropertyAnimation>

class OpacityAnimation
{
public:
    OpacityAnimation(QWidget* widget, double opacity, int duration, QEasingCurve easingCurve);

    // 初始化不透明度，初始化动画
    void startAnimation(double start_opacity, double goal_opacity);
    // 直接设置不透明度
	void setOpacity(double opacity);

    // 控件对象指针
	QWidget* m_widget = nullptr;
    // 不透明度效果对象
    QGraphicsOpacityEffect* m_opacityEffect = nullptr;
    // 动画对象
    QPropertyAnimation* m_animation_obj = nullptr;
};

#endif // OPACITYANIMATION_H
