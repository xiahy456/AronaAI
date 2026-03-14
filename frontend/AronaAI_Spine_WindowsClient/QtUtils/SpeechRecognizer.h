#ifndef SPEECHRECOGNIZE_H
#define SPEECHRECOGNIZE_H

#include <Defines.h>

#include <QObject>
#include <QString>
#include <QDebug>
#include <vosk_api.h>

class SpeechRecognizer : public QObject
{
    Q_OBJECT

public:
    explicit SpeechRecognizer(QObject* parent = nullptr);
    ~SpeechRecognizer();

    // 初始化Vosk模型
    bool initialize(const QString& modelPath);

    // 识别音频数据
    QString recognize(const QByteArray& audioData);

    // 检查是否已初始化
    bool isInitialized() const;

signals:
    void errorOccurred(const QString& error);

private:
    VoskModel* m_model;
    VoskRecognizer* m_recognizer;
    bool m_initialized;
};

#endif // SPEECHRECOGNIZE_H