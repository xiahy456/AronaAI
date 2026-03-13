#ifndef SPINE_QTTEXTURELOADER_H
#define SPINE_QTTEXTURELOADER_H

#include <Defines.h>

#include <spine/TextureLoader.h>
#include <spine/Atlas.h>
#include <QOpenGLWidget>
#include <QOpenGLFunctions>
#include <QOpenGLShaderProgram>
#include <QOpenGLBuffer>
#include <QOpenGLVertexArrayObject>
#include <QOpenGLTexture>
#include <QOpenGLContext>
#include <QDebug>
#include <QImage>
#include <unordered_map>

class QtTextureLoader : public spine::TextureLoader {
public:
    virtual void load(spine::AtlasPage& page, const spine::String& path) override;
    virtual void unload(void* texture) override;

private:
    std::unordered_map<GLuint, QOpenGLTexture*> m_textureMap;
};

#endif // SPINE_QTTEXTURELOADER_H