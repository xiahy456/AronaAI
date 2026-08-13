/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

#ifndef QTSPINEWIDGET_H
#define QTSPINEWIDGET_H

#include <spine/QtTextureLoader.h>

#include <GlobalInclude.h>

#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLBuffer>
#include <QOpenGLVertexArrayObject>
#include <QTimer>
#include <QElapsedTimer>
#include <QVector>
#include <QOpenGLTexture>
#include <QOpenGLExtraFunctions>
#include <QFrame>
#include <QPoint>
#include <QMouseEvent>
#include <QCoreApplication>
#include <QApplication>

#include <memory>

namespace spine {
    class SkeletonData;
    class Skeleton;
    class AnimationStateData;
    class AnimationState;
    class Atlas;
    class SkeletonBinary;
    class SkeletonJson;
    class RegionAttachment;
    class MeshAttachment;
    class Slot;
    class Color;
}

class QtSpineManager : public QOpenGLWidget, protected QOpenGLFunctions
{
    Q_OBJECT

public:
    struct SpineVertex {
        float x, y;        // 位置
        float u, v;        // 纹理坐标
        float r, g, b, a;  // 颜色
    };

    struct TextureBatch {
        GLuint textureId;
        bool premultiplied = false;
        QVector<SpineVertex> vertices;
    };

    explicit QtSpineManager(QWidget* parent = nullptr);
    ~QtSpineManager();

    bool isGLReady() const { return m_glReady; }

    void loadSpineFile(const QString& atlasPath, const QString& skelOrJsonPath);
    void setAnimation(const QString& name, int track_idx, bool loop = true);
	void clearAnimation(int track_idx, float mix_duration);

    // 摸头相关函数

signals:
    void spineLoaded();
    void glReady();

protected:
    // 重写OpenGL相关函数
    void initializeGL() override;
    void paintGL() override;
    void resizeGL(int w, int h) override;

    // 重写鼠标事件
    void mousePressEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;

private slots:
    // 更新动画
    void updateAnimation();
	// 长按事件处理函数
    void onLongTouchTimeout();

private:
    // 辅助函数
    GLuint getTextureId(spine::RegionAttachment* attachment);
    GLuint getTextureId(spine::MeshAttachment* attachment);
    bool getTexturePremultiplied(spine::RegionAttachment* attachment);
    bool getTexturePremultiplied(spine::MeshAttachment* attachment);
    void collectRegionAttachmentVertices(spine::RegionAttachment* attachment, spine::Slot* slot, const spine::Color& slotColor);
    void collectMeshAttachmentVertices(spine::MeshAttachment* attachment, spine::Slot* slot, const spine::Color& slotColor);
    void flushBatches();
    void setAttachmentRelativeTransform(const QString& slotName, float offsetX, float offsetY, float rotation = 0.0f, float scaleX = 1.0f, float scaleY = 1.0f);
    // 摸头函数
    void handlePat();
    void handlePatEnd();

    // Spine 对象
    spine::Atlas* m_atlas = nullptr;
    QtTextureLoader* m_textureLoader = nullptr;
    spine::SkeletonData* m_skeletonData = nullptr;
    spine::Skeleton* m_skeleton = nullptr;
    spine::AnimationStateData* m_animationStateData = nullptr;
    spine::AnimationState* m_animationState = nullptr;

    // 骨骼显示位置（用于坐标转换）
    float m_spineX = 0.0f;
    float m_spineY = 0.0f;
    float m_scale = 1.0f;

    // 定时器
    QTimer m_timer;
    QElapsedTimer m_elapsedTimer;
    float m_lastTime = 0.0f;

    // 摸摸头
    QTimer m_longTouchTimer;    // 长按计时器
	bool m_isLongTouch = false; // 是否处于长按状态

    // OpenGL 资源
    QOpenGLShaderProgram* m_program = nullptr;
    QOpenGLBuffer* m_vbo = nullptr;
    QOpenGLVertexArrayObject* m_vao = nullptr;
    bool m_glReady = false;

    // 统一变量位置
    GLint m_u_matrixLoc;
    GLint m_u_textureLoc;
    GLint m_u_premultipliedLoc;

    // 批次数据
    QVector<TextureBatch> m_batches;
};

#endif // QTSPINEWIDGET_H