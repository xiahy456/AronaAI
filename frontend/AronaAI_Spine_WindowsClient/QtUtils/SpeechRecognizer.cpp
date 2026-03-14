#include "SpeechRecognizer.h"

SpeechRecognizer::SpeechRecognizer(QObject* parent)
    : QObject(parent)
    , m_model(nullptr)
    , m_recognizer(nullptr)
    , m_initialized(false)
{
}

SpeechRecognizer::~SpeechRecognizer()
{
    if (m_recognizer) {
        vosk_recognizer_free(m_recognizer);
        m_recognizer = nullptr;
    }
    if (m_model) {
        vosk_model_free(m_model);
        m_model = nullptr;
    }
}

bool SpeechRecognizer::initialize(const QString& modelPath)
{
    if (m_initialized) {
        qDebug().noquote() << FINE_PR << "[Vosk]Already initialized";
        return true;
    }

    // 加载Vosk模型
    m_model = vosk_model_new(modelPath.toStdString().c_str());
    if (!m_model) {
        QString error = "[Vosk]Failed to load vosk! Please check out the model path: " + modelPath;
        qWarning().noquote() << ERROR_PR << error;
        emit errorOccurred(error);
        return false;
    }

    // 创建识别器（采样率16000Hz）
    m_recognizer = vosk_recognizer_new(m_model, 16000.0f);
    if (!m_recognizer) {
        vosk_model_free(m_model);
        m_model = nullptr;
        emit errorOccurred("[Vosk]Failed to create vosk recognizer!");
        return false;
    }

    m_initialized = true;
    qDebug().noquote() << FINE_PR << "[Vosk]Vosk initialized successfully!";
    return true;
}

QString SpeechRecognizer::recognize(const QByteArray& audioData)
{
    if (!m_initialized) {
        qWarning().noquote() << ERROR_PR << "[Vosk]Recognizer not initialized!";
        return QString();
    }

    if (audioData.isEmpty()) {
        qWarning().noquote() << ERROR_PR << "[Vosk]Audio data is empty!";
        return QString();
    }

    // 重置识别器状态
    vosk_recognizer_reset(m_recognizer);

    // 识别音频数据
    if (vosk_recognizer_accept_waveform(m_recognizer, audioData.data(), audioData.size())) {
        // 获取最终结果
        const char* result = vosk_recognizer_result(m_recognizer);
        QString resultStr = QString::fromUtf8(result);
        qDebug().noquote() << FINE_PR << "[Vosk]Final result:" << resultStr;
        return resultStr;
    }
    else {
        // 获取部分结果（这里只获取最终结果）
        const char* partial = vosk_recognizer_partial_result(m_recognizer);
        QString partialStr = QString::fromUtf8(partial);
        qDebug().noquote() << FINE_PR << "[Vosk]Partial result:" << partialStr;
        return partialStr;
    }
}

bool SpeechRecognizer::isInitialized() const
{
    return m_initialized;
}