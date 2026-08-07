#pragma once
// ParallelogramButton.h
#ifndef PARALLELOGRAMBUTTON_H
#define PARALLELOGRAMBUTTON_H

#include <QPushButton>
#include <QPainter>
#include <QPainterPath>
#include <QEvent>
#include <QMouseEvent>

class ParallelogramButton : public QPushButton
{
    Q_OBJECT
public:
    explicit ParallelogramButton(QWidget* parent = nullptr);

    void setShearValue(qreal shear);
    void setFillColor(const QColor& color);
    void setHoverColor(const QColor& color);
    void setPressedColor(const QColor& color);
    void setBackgroundImage(const QString& imagePath);
    void setBackgroundImage(const QPixmap& pixmap);
    void setImageScaleMode(Qt::AspectRatioMode mode);  // 图片缩放模式
    void setTextColor(const QColor& color);
	void setBorderWidth(int width);

protected:
    void paintEvent(QPaintEvent* event) override;
    void enterEvent(QEnterEvent* event) override;
    void leaveEvent(QEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    qreal m_shear;          // 倾斜系数
    QColor m_fillColor;     // 填充颜色
    QColor m_hoverColor;    // 悬停颜色
    QColor m_pressedColor;  // 按下颜色
    bool m_isHovered;       // 是否悬停
    bool m_isPressed;       // 是否按下
    QPixmap m_backgroundImage;  // 背景图片
    bool m_hasBackgroundImage;  // 是否有背景图片
    Qt::AspectRatioMode m_imageScaleMode;  // 图片缩放模式
    QColor m_textColor = QColor(44, 69, 99);  // 默认深蓝色
    int m_borderWidth = 0;
};

#endif