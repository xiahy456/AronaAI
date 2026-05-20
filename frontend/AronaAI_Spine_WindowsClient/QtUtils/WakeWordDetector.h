#pragma once

#include <QObject>
#include <QVector>

struct SherpaOnnxKeywordSpotter;
struct SherpaOnnxOnlineStream;

class WakeWordDetector : public QObject
{
    Q_OBJECT

public:
    explicit WakeWordDetector(QObject* parent = nullptr);
    ~WakeWordDetector();

    bool initialize(const QString& modelDir, const QString& keywordsFile);
    bool isInitialized() const { return m_initialized; }
    bool isDegraded() const { return m_degraded; }

    // Feed int16 PCM samples (16kHz, mono) for wake word detection
    void processFrame(const QVector<float>& samples);

signals:
    void wakeWordDetected(const QString& keyword);
    void errorOccurred(const QString& error);

private:
    const SherpaOnnxKeywordSpotter* m_kws = nullptr;
    const SherpaOnnxOnlineStream* m_stream = nullptr;
    bool m_initialized = false;
    bool m_degraded = false;
};
