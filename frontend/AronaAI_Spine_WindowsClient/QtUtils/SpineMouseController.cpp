// SpineMouseController.cpp
#include "SpineMouseController.h"
#include <cmath>
#include <QDebug>

SpineMouseController::SpineMouseController(QObject* parent)
    : QObject(parent)
{
    // 初始化更新定时器（50fps）
    m_updateTimer.setInterval(20);
    connect(&m_updateTimer, &QTimer::timeout, this, &SpineMouseController::onUpdateEyes);
    m_updateTimer.start();

    // 连接长按定时器
    connect(&m_longTouchTimer, &QTimer::timeout, this, &SpineMouseController::onLongTouchTimeout);
    m_longTouchTimer.setSingleShot(true);
    m_longTouchTimer.setInterval(100);
}

SpineMouseController::~SpineMouseController()
{
    m_updateTimer.stop();
    m_longTouchTimer.stop();
}

void SpineMouseController::initialize(spine::Skeleton* skeleton, spine::AnimationState* animationState,
    const QString& touchBoneName, const QString& headAnimationPrefix)
{
    m_skeleton = skeleton;
    m_animationState = animationState;
    m_touchBoneName = touchBoneName;

    if (m_skeleton) {
        m_touchBone = m_skeleton->findBone(touchBoneName.toStdString().c_str());
    }

    // 设置默认头部动画名称
    m_headAnimation = headAnimationPrefix;
    m_headAnimationEnd = headAnimationPrefix + "End";
}

void SpineMouseController::handleMousePress(const QPointF& globalPos, const QPointF& localPos,
    float spineX, float spineY, float scale)
{
    if (!m_touchBone) return;

    m_state.mouseDown = true;

    // 启动长按定时器
    m_longTouchTimer.start();

    // 计算触摸点相对于角色的坐标
    QPointF relativePoint = worldToLocal(globalPos, spineX, spineY, scale);
    QPointF boneLocalPoint = localToBone(relativePoint);

    // 判断是否触摸到头部
    m_state.patHead = isPointNearHead(boneLocalPoint, scale);
    emit headTouched(m_state.patHead);

    // 记录鼠标位置
    m_state.mouseLocalPoint = boneLocalPoint;
}

void SpineMouseController::handleMouseRelease(const QPointF& globalPos)
{
    // 停止长按定时器
    m_longTouchTimer.stop();

    // 如果不是长按且启用了穿透，触发对话
    if (!m_state.longTouch && m_penetration) {
        emit talkTriggered(m_state.talkIndex);
        m_state.talkCount++;
    }

    // 如果触摸到头部且是长按且没有正在播放动画，播放头部动画结束
    if (m_state.patHead && m_state.longTouch && !m_state.isAnimation) {
        playHeadAnimationEnd();
    }

    // 重置状态
    m_state.mouseLocalPoint = QPointF(0, 0);
    m_state.mouseDown = false;
    m_state.longTouch = false;
    m_state.patHead = false;
    emit headTouched(false);
    emit longTouchTriggered(false);
}

void SpineMouseController::handleMouseMove(const QPointF& globalPos, const QPointF& localPos,
    float spineX, float spineY, float scale)
{
    // 鼠标轨迹追踪
    if (m_mouseTrial) {
        // 可以在这里记录鼠标轨迹，用于特殊效果
    }

    // 鼠标追踪或长按时更新眼睛注视点
    if (m_mouseTracking || m_state.longTouch) {
        QPointF relativePoint = worldToLocal(globalPos, spineX, spineY, scale);
        QPointF boneLocalPoint = localToBone(relativePoint);

        m_state.mouseLocalPoint = boneLocalPoint;
    }
}

void SpineMouseController::onLongTouchTimeout()
{
    if (!m_state.mouseDown) return;

    m_state.longTouch = true;
    emit longTouchTriggered(true);

    // 如果触摸到头部且没有正在播放动画，播放头部动画
    if (m_state.patHead && !m_state.isAnimation) {
        playHeadAnimation(true);
    }
}

void SpineMouseController::onUpdateEyes()
{
    if (!m_touchBone || !m_skeleton) return;

    // 限制眼睛移动范围
    QPointF clampedPoint = clampVectorLength(m_state.mouseLocalPoint, m_eyeRadius);

    // 获取当前骨骼位置
    float currentX = m_touchBone->getX();
    float currentY = m_touchBone->getY();

    // 平滑移动眼睛位置
    if (std::abs(currentX - clampedPoint.x()) > 1.0f ||
        std::abs(currentY - clampedPoint.y()) > 1.0f) {

        float newX = (currentX + clampedPoint.x()) / m_state.linearAlgebraScale;
        float newY = (currentY + clampedPoint.y()) / m_state.linearAlgebraScale;

        m_touchBone->setX(newX);
        m_touchBone->setY(newY);

        // 更新骨骼世界变换
        m_skeleton->updateWorldTransform(spine::Physics_Update);
    }
}

QPointF SpineMouseController::worldToLocal(const QPointF& worldPoint,
    float spineX, float spineY, float scale)
{
    QPointF result;
    result.setX((worldPoint.x() - spineX) / scale);
    result.setY((worldPoint.y() - spineY) / scale);
    return result;
}

QPointF SpineMouseController::localToBone(const QPointF& localPoint)
{
    if (!m_touchBone) return localPoint;

    // 直接使用骨骼的worldToLocal方法
    // 注意：localPoint已经是相对于spine显示位置的坐标
    float outX, outY;
    m_touchBone->worldToLocal(localPoint.x(), localPoint.y(), outX, outY);
    return QPointF(outX, outY);
}

float SpineMouseController::vectorLength(const QPointF& vec) const
{
    return std::sqrt(vec.x() * vec.x() + vec.y() * vec.y());
}

QPointF SpineMouseController::clampVectorLength(const QPointF& vec, float maxLength) const
{
    float length = vectorLength(vec);
    if (length > maxLength && length > 0) {
        float scale = maxLength / length;
        return QPointF(vec.x() * scale, vec.y() * scale);
    }
    return vec;
}

bool SpineMouseController::isPointNearHead(const QPointF& point, float scale) const
{
    float length = vectorLength(point);
    return length <= (400.0f * scale);
}

void SpineMouseController::playHeadAnimation(bool isTouch)
{
    if (!m_animationState) return;

    m_state.isAnimation = true;

    std::string animA = (m_headAnimation + "_A").toStdString();
    std::string animM = (m_headAnimation + "_M").toStdString();

    m_animationState->setAnimation(5, animA.c_str(), false);
    m_animationState->setAnimation(6, animM.c_str(), false);

    // 动画结束时重置状态
    // 可以通过AnimationState的监听器来实现
}

void SpineMouseController::playHeadAnimationEnd()
{
    if (!m_animationState) return;

    std::string animA = (m_headAnimationEnd + "_A").toStdString();
    std::string animM = (m_headAnimationEnd + "_M").toStdString();

    m_animationState->setAnimation(5, animA.c_str(), false);
    m_animationState->setAnimation(6, animM.c_str(), false);

    m_state.isAnimation = false;
}