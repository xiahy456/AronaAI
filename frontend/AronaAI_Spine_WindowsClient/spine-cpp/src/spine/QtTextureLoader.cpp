#include <spine/QtTextureLoader.h>

void QtTextureLoader::load(spine::AtlasPage& page, const spine::String& path) {
    std::string pathStr(path.buffer());
    QString qImgPath = QString::fromStdString(pathStr);

    // 使用QImage加载图片
    QImage image;
    if (!image.load(qImgPath)) {
        qDebug() << "[Spine Operation] Texture Load Failed! Texture：" << qImgPath;
        return;
    }

    qDebug() << "[Spine Operation] Original image format:" << image.format()
        << "Size:" << image.width() << "x" << image.height()
        << "Has Alpha:" << image.hasAlphaChannel();

    // 确保图片是RGBA格式
    if (image.format() != QImage::Format_RGBA8888) {
        image = image.convertToFormat(QImage::Format_RGBA8888);
    }

    // 不要修改RGB值，只保留原始颜色，预乘Alpha处理应该在着色器中进行，而不是在这里

    // 创建OpenGL纹理
    QOpenGLTexture* glTexture = new QOpenGLTexture(image.mirrored());
    glTexture->setMinificationFilter(QOpenGLTexture::Linear);
    glTexture->setMagnificationFilter(QOpenGLTexture::Linear);
    glTexture->setWrapMode(QOpenGLTexture::ClampToEdge);

    // 获取纹理ID
    GLuint textureId = glTexture->textureId();

    // 存储纹理ID到page.texture
    GLuint* textureIdPtr = new GLuint(textureId);
    page.texture = textureIdPtr;

    // 同时也存储QOpenGLTexture指针以便正确释放
    m_textureMap[textureId] = glTexture;

    // 设置大图的实际像素宽高
    page.width = image.width();
    page.height = image.height();

    qDebug() << "[Spine Operation] Texture Load Succeed! "
        << " Path: " << qImgPath
        << "| Size: " << page.width << "x" << page.height
        << "| Texture ID: " << textureId;
}

void QtTextureLoader::unload(void* texture) {
    GLuint* textureIdPtr = static_cast<GLuint*>(texture);
    if (textureIdPtr) {
        GLuint textureId = *textureIdPtr;

        // 查找并删除QOpenGLTexture对象
        auto it = m_textureMap.find(textureId);
        if (it != m_textureMap.end()) {
            delete it->second;  // QOpenGLTexture析构函数会自动调用glDeleteTextures
            m_textureMap.erase(it);
        }

        // 删除纹理ID指针
        delete textureIdPtr;
    }
    qDebug() << "[Spine Operation] Texture Unload Succeed! ";
}