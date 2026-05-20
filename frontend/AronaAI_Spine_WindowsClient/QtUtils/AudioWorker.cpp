#include "AudioWorker.h"
#include "WakeWordDetector.h"
#include "Defines.h"
#include "sherpa-onnx/c-api/c-api.h"

#include <QDebug>

AudioWorker::AudioWorker(QObject* parent)
    : QObject(parent)
{
    m_detector = new WakeWordDetector(this);
    connect(m_detector, &WakeWordDetector::wakeWordDetected,
            this, &AudioWorker::wakeWordDetected);
    connect(m_detector, &WakeWordDetector::errorOccurred,
            this, &AudioWorker::errorOccurred);

    // VAD check timer — fires every 100ms to poll for completed speech segments
    m_vadCheckTimer = new QTimer(this);
    m_vadCheckTimer->setTimerType(Qt::PreciseTimer);
    connect(m_vadCheckTimer, &QTimer::timeout, this, &AudioWorker::checkVad);
}

AudioWorker::~AudioWorker()
{
    if (m_vad) {
        SherpaOnnxDestroyVoiceActivityDetector(m_vad);
        m_vad = nullptr;
    }
}

bool AudioWorker::initialize(const QString& modelDir, const QString& keywordsFile)
{
    return m_detector->initialize(modelDir, keywordsFile);
}

bool AudioWorker::initializeVad(const QString& vadModelPath, float silenceDurationSec)
{
    if (m_vad) return true;

    QByteArray vadPath = vadModelPath.toUtf8();
    if (!SherpaOnnxFileExists(vadPath.constData())) {
        FINE_DEBUG_OUTPUT("[AudioWorker] VAD model not found: " + vadModelPath);
        return false;
    }

    SherpaOnnxVadModelConfig config;
    memset(&config, 0, sizeof(config));
    config.silero_vad.model = vadPath.constData();
    config.silero_vad.threshold = 0.5f;
    config.silero_vad.min_silence_duration = silenceDurationSec;
    config.silero_vad.min_speech_duration = 0.25f;
    config.silero_vad.max_speech_duration = 20.0f;
    config.silero_vad.window_size = 512;
    config.sample_rate = 16000;
    config.num_threads = 1;
    config.debug = 0;

    m_vadWindowSize = config.silero_vad.window_size;
    m_vad = SherpaOnnxCreateVoiceActivityDetector(&config, 60.0f);
    if (!m_vad) {
        FINE_DEBUG_OUTPUT("[AudioWorker] Failed to create VAD detector");
        return false;
    }

    FINE_DEBUG_OUTPUT("[AudioWorker] VAD initialized (silence threshold: " +
                      QString::number(silenceDurationSec) + "s)");
    return true;
}

bool AudioWorker::isDegraded() const
{
    return m_detector->isDegraded();
}

QVector<float> AudioWorker::int16ToFloat(const QByteArray& chunk)
{
    const int16_t* raw = reinterpret_cast<const int16_t*>(chunk.constData());
    int n = chunk.size() / 2;
    QVector<float> samples(n);
    for (int i = 0; i < n; ++i) {
        samples[i] = raw[i] / 32768.0f;
    }
    return samples;
}

void AudioWorker::onAudioChunk(const QByteArray& chunk)
{
    QVector<float> samples = int16ToFloat(chunk);

    // Always feed KWS for wake word detection
    m_detector->processFrame(samples);

    // If recording utterance, buffer and feed VAD
    if (m_recording && m_vad) {
        m_utteranceBuffer.append(chunk);
        SherpaOnnxVoiceActivityDetectorAcceptWaveform(m_vad,
            samples.constData(), samples.size());
    }
}

void AudioWorker::startRecordingUtterance()
{
    if (!m_vad) {
        FINE_DEBUG_OUTPUT("[AudioWorker] VAD not ready, skipping utterance recording");
        return;
    }

    m_utteranceBuffer.clear();
    SherpaOnnxVoiceActivityDetectorReset(m_vad);
    m_recording = true;
    m_vadCheckTimer->start(100);
    FINE_DEBUG_OUTPUT("[AudioWorker] Utterance recording started (VAD active)");
}

void AudioWorker::checkVad()
{
    if (!m_vad || !m_recording) return;

    // Check if VAD has detected a completed speech segment
    while (!SherpaOnnxVoiceActivityDetectorEmpty(m_vad)) {
        const SherpaOnnxSpeechSegment* seg = SherpaOnnxVoiceActivityDetectorFront(m_vad);

        // Speech detected → user stopped speaking
        if (seg && seg->n > 0) {
            FINE_DEBUG_OUTPUT("[AudioWorker] VAD detected end of speech, utterance size: " +
                              QString::number(m_utteranceBuffer.size()) + " bytes");

            m_recording = false;
            m_vadCheckTimer->stop();
            SherpaOnnxVoiceActivityDetectorReset(m_vad);

            QByteArray result = m_utteranceBuffer;
            m_utteranceBuffer.clear();

            emit utteranceComplete(result);
            SherpaOnnxDestroySpeechSegment(seg);
            SherpaOnnxVoiceActivityDetectorPop(m_vad);
            return;
        }

        SherpaOnnxDestroySpeechSegment(seg);
        SherpaOnnxVoiceActivityDetectorPop(m_vad);
    }
}
