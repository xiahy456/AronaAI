// BlueakaFontLoader.cpp
#include "BlueakaFontLoader.h"
#include <QFontDatabase>
#include <QDir>
#include <QDebug>
#include <QApplication>
#include <QFileInfo>

BlueakaFontLoader* BlueakaFontLoader::m_instance = nullptr;

BlueakaFontLoader* BlueakaFontLoader::instance()
{
    if (!m_instance) {
        m_instance = new BlueakaFontLoader(qApp);
    }
    return m_instance;
}

BlueakaFontLoader::BlueakaFontLoader(QObject* parent)
    : QObject(parent)
{
}

BlueakaFontLoader::~BlueakaFontLoader()
{
}

bool BlueakaFontLoader::loadFromDirectory(const QString& directory)
{
    QDir fontDir(directory);
    if (!fontDir.exists()) {
        qWarning().noquote() << ERROR_PR << "[Font Loader]Font directory not found:" << directory;
        return false;
    }

    // 获取所有 TTF 文件
    QStringList filters;
    filters << "*.ttf" << "*.otf";
    QFileInfoList fontFiles = fontDir.entryInfoList(filters, QDir::Files);

    if (fontFiles.isEmpty()) {
        qWarning() << ERROR_PR << "[Font Loader]No TTF/OTF files found in:" << directory;
        return false;
    }

    qDebug().noquote() << FINE_PR << "[Font Loader]Found" << fontFiles.size() << "font files";

    QFontDatabase fontDb;
    int loadedCount = 0;

    for (const QFileInfo& fontFile : fontFiles) {
        QString fontPath = fontFile.absoluteFilePath();
        int fontId = fontDb.addApplicationFont(fontPath);

        if (fontId != -1) {
            loadedCount++;
            m_loadedFiles << fontPath;

            // 获取字体族名称
            QStringList families = fontDb.applicationFontFamilies(fontId);
            for (const QString& family : families) {
                if (!m_fontFamilies.contains(family)) {
                    m_fontFamilies << family;
                }
            }

            qDebug().noquote() << FINE_PR << "[Font Loader]Loaded:" << fontFile.fileName() << "->" << families;
        }
        else {
            qWarning() << ERROR_PR << "[Font Loader]Failed:" << fontFile.fileName();
        }
    }

    qDebug().noquote() << FINE_PR << "[Font Loader]Total loaded:" << loadedCount << "fonts";
    qDebug().noquote() << FINE_PR << "[Font Loader]Font families:" << m_fontFamilies;

    return !m_fontFamilies.isEmpty();
}

bool BlueakaFontLoader::loadFromResource(const QString& resourcePath)
{
    QDir fontDir(resourcePath);
    return loadFromDirectory(resourcePath);
}

QFont BlueakaFontLoader::createFont(int pointSize, bool bold, bool italic)
{
    if (m_fontFamilies.isEmpty()) {
        qWarning() << ERROR_PR << "[Font Loader]No Blueaka font loaded, using default font";
        return QFont();
    }

    QFont font;
    font.setFamily(m_fontFamilies.first());
    font.setPointSize(pointSize);
    font.setBold(bold);
    font.setItalic(italic);

    return font;
}

QFont BlueakaFontLoader::createFont(int pointSize, QFont::Weight weight, bool italic)
{
    if (m_fontFamilies.isEmpty()) {
        qWarning() << ERROR_PR << "[Font Loader]No Blueaka font loaded, using default font";
        return QFont();
    }

    QFont font;
    font.setFamily(m_fontFamilies.first());
    font.setPointSize(pointSize);
    font.setWeight(weight);
    font.setItalic(italic);

    return font;
}