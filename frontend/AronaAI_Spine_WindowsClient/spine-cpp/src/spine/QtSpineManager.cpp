#include "spine/QtSpineManager.h"
#include "spine/QtTextureLoader.h"
#include <spine/Atlas.h>
#include <spine/SkeletonData.h>
#include <spine/Skeleton.h>
#include <spine/AnimationStateData.h>
#include <spine/AnimationState.h>
#include <spine/SkeletonBinary.h>
#include <spine/SkeletonJson.h>
#include <spine/RegionAttachment.h>
#include <spine/MeshAttachment.h>
#include <spine/Slot.h>
#include <QDebug>
#include <QMatrix4x4>

QtSpineManager::QtSpineManager(QWidget* parent) : QOpenGLWidget(parent)
{
    // 窗口控件
    this->setAttribute(Qt::WA_TranslucentBackground);	// 设置窗口背景透明
    //this->setAttribute(Qt::WA_TransparentForMouseEvents, true); // 设置鼠标穿透点击
    this->setWindowFlag(Qt::FramelessWindowHint);	// 设置无边框窗口
    this->setWindowFlag(Qt::WindowStaysOnTopHint);	// 设置窗口始终在顶部
    //this->setWindowFlag(Qt::Tool);	// 隐藏应用程序图标
	//this->setWindowOpacity(0.5);    // 设置窗口半透明（0.0完全透明，1.0完全不透明）
	this->setAutoFillBackground(false);   // 禁用自动填充背景，确保paintGL的背景颜色生效
    this->resize(220, 290); // 设置窗口大小

    // 启动事件过滤器
    this->installEventFilter(this);

    // 移动窗口
    // 获取主屏幕
    QScreen* screen = QApplication::primaryScreen();
    QRect screenRect = screen->availableGeometry();
    // 计算左下角位置
    int x = screenRect.left();
    int y = screenRect.bottom() - this->height() + 50;
    // 移动窗口
    this->move(x, y);

    // 动画计时器
    connect(&m_timer, &QTimer::timeout, this, &QtSpineManager::updateAnimation);
    m_timer.start(16);

}

QtSpineManager::~QtSpineManager()
{
    makeCurrent();

    delete m_vbo;
    delete m_vao;
    delete m_program;
    m_batches.clear();

    doneCurrent();

    delete m_animationState;
    delete m_animationStateData;
    delete m_skeleton;
    delete m_skeletonData;
    delete m_atlas;
    delete m_textureLoader;
}

void QtSpineManager::initializeGL()
{
    initializeOpenGLFunctions();

    //glClearColor(0.69f, 0.88f, 0.90f, 0.0f);
    glClearColor(0.0f, 0.0f, 0.0f, 0.0f);  // 完全透明黑色
    // 启用混合，使用正确的混合函数
    glEnable(GL_BLEND);
    glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE, GL_ONE_MINUS_SRC_ALPHA);

    glDisable(GL_DEPTH_TEST);

    // 创建着色器程序
    m_program = new QOpenGLShaderProgram();

    const char* vertexShaderSource =
        "#version 330 core\n"
        "uniform mat4 u_matrix;\n"
        "layout(location = 0) in vec2 a_position;\n"
        "layout(location = 1) in vec2 a_texCoord;\n"
        "layout(location = 2) in vec4 a_color;\n"
        "out vec2 v_texCoord;\n"
        "out vec4 v_color;\n"
        "void main() {\n"
        "    gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);\n"
        "    v_texCoord = vec2(a_texCoord.x, 1.0 - a_texCoord.y);\n"
        "    v_color = a_color;\n"
        "}\n";

    const char* fragmentShaderSource =
        "#version 330 core\n"
        "uniform sampler2D u_texture;\n"
        "in vec2 v_texCoord;\n"
        "in vec4 v_color;\n"
        "out vec4 fragColor;\n"
        "void main() {\n"
        "    vec4 texColor = texture(u_texture, v_texCoord);\n"
        "    \n"
        "    // 关键步骤：还原预乘的RGB值\n"
        "    if (texColor.a > 0.0) {\n"
        "        texColor.rgb /= texColor.a;\n"
        "    }\n"
        "    \n"
        "    // 再乘以顶点颜色\n"
        "    fragColor = texColor * v_color;\n"
        "    \n"
        "    // 丢弃几乎透明的像素\n"
        "    if (fragColor.a < 0.01) discard;\n"
        "}\n";

    m_program->addShaderFromSourceCode(QOpenGLShader::Vertex, vertexShaderSource);
    m_program->addShaderFromSourceCode(QOpenGLShader::Fragment, fragmentShaderSource);
    m_program->link();

    m_u_matrixLoc = m_program->uniformLocation("u_matrix");
    m_u_textureLoc = m_program->uniformLocation("u_texture");

    // 创建VBO
    m_vbo = new QOpenGLBuffer(QOpenGLBuffer::VertexBuffer);
    m_vbo->create();
    m_vbo->setUsagePattern(QOpenGLBuffer::DynamicDraw);

    // 创建VAO
    m_vao = new QOpenGLVertexArrayObject();
    m_vao->create();

    qDebug() << "[Spine Operation]OpenGL initialized successfully";
}

void QtSpineManager::paintGL()
{
    glClear(GL_COLOR_BUFFER_BIT);

    if (!m_skeleton || !m_program || !m_program->isLinked()) {
        return;
    }

    // 设置投影矩阵 - 移除视图变换，让骨骼在原始位置
    QMatrix4x4 projection;
    int w = width();
    int h = height();

    // 使用正交投影，Y轴向下以匹配屏幕坐标
    projection.ortho(0, w, h, 0, -1, 1);

    // 创建视图矩阵，用于移动整个Spine动画
    QMatrix4x4 transform;
    transform.translate(110.0f, 270.0f);
    transform.scale(0.2f, -0.2f);

    // 组合矩阵：最终位置 = 投影 * 视图
    QMatrix4x4 matrix = projection * transform;

    m_program->bind();
    m_program->setUniformValue(m_u_matrixLoc, matrix);
    m_program->setUniformValue(m_u_textureLoc, 0);

    m_batches.clear();

    // 收集所有顶点数据
    spine::Vector<spine::Slot*>& slots_rev = m_skeleton->getSlots();
    for (size_t i = 0; i < slots_rev.size(); ++i) {
        spine::Slot* slot = slots_rev[i];
        if (!slot) continue;

        spine::Attachment* attachment = slot->getAttachment();
        if (!attachment) continue;

        spine::Color color = slot->getColor();

        if (attachment->getRTTI().instanceOf(spine::RegionAttachment::rtti)) {
            auto* regionAttachment = static_cast<spine::RegionAttachment*>(attachment);
            collectRegionAttachmentVertices(regionAttachment, slot, color);
        }
        else if (attachment->getRTTI().instanceOf(spine::MeshAttachment::rtti)) {
            auto* meshAttachment = static_cast<spine::MeshAttachment*>(attachment);
            collectMeshAttachmentVertices(meshAttachment, slot, color);
        }
    }

    // 渲染所有批次
    flushBatches();

    m_program->release();
}

void QtSpineManager::resizeGL(int w, int h)
{
    glViewport(0, 0, w, h);
}

void QtSpineManager::updateAnimation()
{
    if (!m_animationState || !m_skeleton) {
        return;
    }

    // 使用QElapsedTimer计算时间差
    float now = m_elapsedTimer.elapsed() / 1000.0f;
    if (m_lastTime == 0.0f) {
        m_lastTime = now;
        m_elapsedTimer.start();
        return;
    }

    float deltaTime = now - m_lastTime;
    m_lastTime = now;

    // 限制最大deltaTime，避免卡顿时跳跃太大
    if (deltaTime > 0.1f) deltaTime = 0.1f;
    if (deltaTime < 0.001f) return; // 时间差太小就不更新

    // 更新动画
    m_animationState->update(deltaTime);
    m_animationState->apply(*m_skeleton);
    m_skeleton->updateWorldTransform(spine::Physics_Update);

    // 请求重绘
    update();
}

void QtSpineManager::loadSpineFile(const QString& atlasPath, const QString& skelOrJsonPath)
{
    m_textureLoader = new QtTextureLoader();
    m_atlas = new spine::Atlas(atlasPath.toStdString().c_str(), m_textureLoader);

    if (!m_atlas) {
        qCritical() << "Failed to load atlas:" << atlasPath;
        return;
    }

    // 设置图集的PMA标志（通常Spine图集使用预乘Alpha）
    for (int i = 0; i < m_atlas->getPages().size(); i++) {
        spine::AtlasPage* page = m_atlas->getPages()[i];
        if (page) {
            // 通常Spine导出的图集使用预乘Alpha
            page->pma = true;
        }
    }

    bool isBinary = skelOrJsonPath.endsWith(".skel", Qt::CaseInsensitive);

    if (isBinary) {
        spine::SkeletonBinary binary(m_atlas);
        //binary.setScale(0.3f);
        m_skeletonData = binary.readSkeletonDataFile(skelOrJsonPath.toStdString().c_str());
    }
    else {
        spine::SkeletonJson json(m_atlas);
        //json.setScale(0.3f);
        m_skeletonData = json.readSkeletonDataFile(skelOrJsonPath.toStdString().c_str());
    }

    if (!m_skeletonData) {
        qCritical() << "Failed to load skeleton data:" << skelOrJsonPath;
        return;
    }

    m_skeleton = new spine::Skeleton(m_skeletonData);
    m_animationStateData = new spine::AnimationStateData(m_skeletonData);
    // 设置默认混合时间
    m_animationStateData->setDefaultMix(0.2f);
    m_animationState = new spine::AnimationState(m_animationStateData);
    m_skeleton->setToSetupPose();

    qDebug() << "[Spine Operation]Spine file loaded successfully!";
}

void QtSpineManager::setAnimation(const QString& name, int track_idx, bool loop)
{
    if (!m_animationState || !m_skeletonData) {
        qDebug() << "[Spine Operation]Animation state not ready";
        return;
    }

    spine::Animation* anim = m_skeletonData->findAnimation(name.toStdString().c_str());
    if (anim) {
        m_animationState->setAnimation(track_idx, anim, loop);
        m_lastTime = 0;
        qDebug() << "[Spine Operation]Set animation:" << name;
    }
    else {
        qDebug() << "[Spine Operation]Animation not found:" << name;
    }
}

void QtSpineManager::collectMeshAttachmentVertices(spine::MeshAttachment* attachment,
    spine::Slot* slot,
    const spine::Color& slotColor)
{
    if (!attachment || !slot) return;

    GLuint textureId = getTextureId(attachment);
    if (textureId == 0) return;

    int numVertices = attachment->getWorldVerticesLength();
    if (numVertices <= 0) return;

    spine::Vector<unsigned short>& triangles = attachment->getTriangles();
    if (triangles.size() < 3) return;

    spine::Vector<float>& uvs = attachment->getUVs();
    if (uvs.size() < static_cast<size_t>(numVertices)) return;

    // 获取附件的颜色
    spine::Color attachmentColor = attachment->getColor();

    // 计算最终颜色
    float finalR = slotColor.r * attachmentColor.r;
    float finalG = slotColor.g * attachmentColor.g;
    float finalB = slotColor.b * attachmentColor.b;
    float finalA = slotColor.a * attachmentColor.a;

    // 如果透明度为0，跳过渲染
    if (finalA <= 0.0f) return;

    // 查找或创建批次
    TextureBatch* batch = nullptr;
    for (auto& b : m_batches) {
        if (b.textureId == textureId) {
            batch = &b;
            break;
        }
    }

    if (!batch) {
        TextureBatch newBatch;
        newBatch.textureId = textureId;
        m_batches.append(newBatch);
        batch = &m_batches.last();
    }

    // 计算世界坐标
    std::vector<float> worldVertices(numVertices);
    attachment->computeWorldVertices(*slot, 0, numVertices, worldVertices.data(), 0, 2);

    int vertexCount = numVertices / 2;
    int triangleCount = triangles.size() / 3;

    // 处理三角形
    for (int i = 0; i < triangleCount; ++i) {
        int baseIdx = i * 3;
        if (baseIdx + 2 >= (int)triangles.size()) break;

        int idx1 = triangles[baseIdx];
        int idx2 = triangles[baseIdx + 1];
        int idx3 = triangles[baseIdx + 2];

        if (idx1 >= vertexCount || idx2 >= vertexCount || idx3 >= vertexCount) continue;

        // 处理三个顶点
        int indices[3] = { idx1, idx2, idx3 };
        for (int j = 0; j < 3; ++j) {
            int idx = indices[j];
            int worldIdx = idx * 2;
            int uvIdx = idx * 2;

            if (worldIdx + 1 >= numVertices || uvIdx + 1 >= (int)uvs.size()) continue;

            SpineVertex vertex;
            vertex.x = worldVertices[worldIdx];
            vertex.y = worldVertices[worldIdx + 1];
            vertex.u = uvs[uvIdx];
            vertex.v = uvs[uvIdx + 1];

            // 使用计算好的颜色
            vertex.r = finalR;
            vertex.g = finalG;
            vertex.b = finalB;
            vertex.a = finalA;

            batch->vertices.append(vertex);
        }
    }
}

void QtSpineManager::collectRegionAttachmentVertices(spine::RegionAttachment* attachment,
    spine::Slot* slot,
    const spine::Color& slotColor)
{
    if (!attachment || !slot) return;

    GLuint textureId = getTextureId(attachment);
    if (textureId == 0) return;

    float worldVertices[8];
    attachment->computeWorldVertices(*slot, worldVertices, 0, 8);

    float uvs[8];
    for (int i = 0; i < 8; i++) {
        if (i < attachment->getUVs().size()) {
            uvs[i] = attachment->getUVs()[i];
        }
    }

    // 获取附件颜色
    spine::Color attachmentColor = attachment->getColor();

    // 计算最终颜色
    float finalR = slotColor.r * attachmentColor.r;
    float finalG = slotColor.g * attachmentColor.g;
    float finalB = slotColor.b * attachmentColor.b;
    float finalA = slotColor.a * attachmentColor.a;

    // 如果透明度为0，跳过渲染
    if (finalA <= 0.0f) return;

    TextureBatch* batch = nullptr;
    for (auto& b : m_batches) {
        if (b.textureId == textureId) {
            batch = &b;
            break;
        }
    }

    if (!batch) {
        TextureBatch newBatch;
        newBatch.textureId = textureId;
        m_batches.append(newBatch);
        batch = &m_batches.last();
    }

    // 三角形1
    batch->vertices.append({ worldVertices[0], worldVertices[1], uvs[0], uvs[1], finalR, finalG, finalB, finalA });
    batch->vertices.append({ worldVertices[2], worldVertices[3], uvs[2], uvs[3], finalR, finalG, finalB, finalA });
    batch->vertices.append({ worldVertices[4], worldVertices[5], uvs[4], uvs[5], finalR, finalG, finalB, finalA });

    // 三角形2
    batch->vertices.append({ worldVertices[2], worldVertices[3], uvs[2], uvs[3], finalR, finalG, finalB, finalA });
    batch->vertices.append({ worldVertices[6], worldVertices[7], uvs[6], uvs[7], finalR, finalG, finalB, finalA });
    batch->vertices.append({ worldVertices[4], worldVertices[5], uvs[4], uvs[5], finalR, finalG, finalB, finalA });
}

void QtSpineManager::flushBatches()
{
    if (m_batches.isEmpty()) return;

    m_vbo->bind();
    m_vao->bind();

    // 设置顶点属性指针
    size_t vertexSize = sizeof(SpineVertex);

    // 位置属性 (2 floats)
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, vertexSize, (void*)offsetof(SpineVertex, x));
    glEnableVertexAttribArray(0);

    // 纹理坐标属性 (2 floats)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, vertexSize, (void*)offsetof(SpineVertex, u));
    glEnableVertexAttribArray(1);

    // 颜色属性 (4 floats)
    glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, vertexSize, (void*)offsetof(SpineVertex, r));
    glEnableVertexAttribArray(2);

    int totalVertices = 0;
    for (const auto& batch : m_batches) {
        totalVertices += batch.vertices.size();
    }

    for (const auto& batch : m_batches) {
        if (batch.vertices.isEmpty() || batch.textureId == 0) continue;

        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, batch.textureId);

        // 设置纹理参数
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

        int dataSize = batch.vertices.size() * sizeof(SpineVertex);
        m_vbo->allocate(batch.vertices.constData(), dataSize);

        glDrawArrays(GL_TRIANGLES, 0, batch.vertices.size());

        GLenum error = glGetError();
        if (error != GL_NO_ERROR) {
            qDebug() << "[Spine Operation]OpenGL error:" << error;
        }
    }

    m_vao->release();
    m_vbo->release();
    m_batches.clear();
}

GLuint QtSpineManager::getTextureId(spine::RegionAttachment* attachment)
{
    if (!attachment) return 0;

    // RegionAttachment可以通过getRegion()获取TextureRegion
    spine::TextureRegion* region = attachment->getRegion();
    if (!region) return 0;

    // 从TextureRegion获取AtlasRegion
    spine::AtlasRegion* atlasRegion = static_cast<spine::AtlasRegion*>(region);
    if (!atlasRegion || !atlasRegion->page) return 0;

    // 直接从page.texture获取纹理ID指针
    GLuint* textureIdPtr = static_cast<GLuint*>(atlasRegion->page->texture);
    if (!textureIdPtr) return 0;

    return *textureIdPtr;
}

GLuint QtSpineManager::getTextureId(spine::MeshAttachment* attachment)
{
    if (!attachment) return 0;

    // MeshAttachment也有getRegion()方法
    spine::TextureRegion* region = attachment->getRegion();
    if (!region) return 0;

    spine::AtlasRegion* atlasRegion = static_cast<spine::AtlasRegion*>(region);
    if (!atlasRegion || !atlasRegion->page) return 0;

    GLuint* textureIdPtr = static_cast<GLuint*>(atlasRegion->page->texture);
    if (!textureIdPtr) return 0;

    return *textureIdPtr;
}

void QtSpineManager::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::RightButton) {
        m_dragging = true;
        m_dragPosition = event->globalPosition().toPoint() - frameGeometry().topLeft();
        event->accept();
    }
}

void QtSpineManager::mouseMoveEvent(QMouseEvent* event)
{
    if (m_dragging && (event->buttons() & Qt::RightButton)) {
        move(event->globalPosition().toPoint() - m_dragPosition);
        event->accept();
    }
}

void QtSpineManager::mouseReleaseEvent(QMouseEvent* event)
{
    if (event->button() == Qt::RightButton) {
        m_dragging = false;
        event->accept();
    }
}

