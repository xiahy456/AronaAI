#ifndef SPINEWIDGET_H
#define SPINEWIDGET_H

#include <spine/QtTextureLoader.h>

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

class MyTextureLoader;

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
        QVector<SpineVertex> vertices;
    };

    explicit QtSpineManager(QWidget* parent = nullptr);
    ~QtSpineManager();

    void loadSpineFile(const QString& atlasPath, const QString& skelOrJsonPath);
    void setAnimation(const QString& name, int track_idx, bool loop = true);

protected:
    void initializeGL() override;
    void paintGL() override;
    void resizeGL(int w, int h) override;

private slots:
    void updateAnimation();

private:
    // Spine 对象
    spine::Atlas* m_atlas = nullptr;
    QtTextureLoader* m_textureLoader = nullptr;
    spine::SkeletonData* m_skeletonData = nullptr;
    spine::Skeleton* m_skeleton = nullptr;
    spine::AnimationStateData* m_animationStateData = nullptr;
    spine::AnimationState* m_animationState = nullptr;

    // 定时器
    QTimer m_timer;
    QElapsedTimer m_elapsedTimer;
    float m_lastTime = 0.0f;

    // OpenGL 资源
    QOpenGLShaderProgram* m_program = nullptr;
    QOpenGLBuffer* m_vbo = nullptr;
    QOpenGLVertexArrayObject* m_vao = nullptr;

    // 统一变量位置
    GLint m_u_matrixLoc;
    GLint m_u_textureLoc;

    // 批次数据
    QVector<TextureBatch> m_batches;

    // 辅助函数
    GLuint getTextureId(spine::RegionAttachment* attachment);
    GLuint getTextureId(spine::MeshAttachment* attachment);
    void collectRegionAttachmentVertices(spine::RegionAttachment* attachment, spine::Slot* slot, const spine::Color& slotColor);
    void collectMeshAttachmentVertices(spine::MeshAttachment* attachment, spine::Slot* slot, const spine::Color& slotColor);
    void flushBatches();
};

#endif // SPINEWIDGET_H