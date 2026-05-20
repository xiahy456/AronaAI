#pragma once

#include <QObject>
#include <QByteArray>
#include <QVector>
#include <QTimer>

class WakeWordDetector;
struct SherpaOnnxVoiceActivityDetector;
struct SherpaOnnxVadModelConfig;

class AudioWorker : public QObject
{
    Q_OBJECT

public:
    explicit AudioWorker(QObject* parent = nullptr);
    ~AudioWorker();

    bool initialize(const QString& modelDir, const QString& keywordsFile);
    bool initializeVad(const QString& vadModelPath, float silenceDurationSec = 1.5f);
    bool isDegraded() const;
    bool isVadReady() const { return m_vad != nullptr; }

public slots:
    void onAudioChunk(const QByteArray& chunk);

    // Called by MainController when wake word is detected
    void startRecordingUtterance();

signals:
    void wakeWordDetected(const QString& keyword);
    void errorOccurred(const QString& error);
    void utteranceComplete(const QByteArray& audioData);  // int16 PCM of recorded command

private slots:
    void checkVad();

private:
    WakeWordDetector* m_detector = nullptr;
    const SherpaOnnxVoiceActivityDetector* m_vad = nullptr;
    QByteArray m_utteranceBuffer;
    QTimer* m_vadCheckTimer = nullptr;
    bool m_recording = false;
    int32_t m_vadWindowSize = 512;

    QVector<float> int16ToFloat(const QByteArray& chunk);
};
