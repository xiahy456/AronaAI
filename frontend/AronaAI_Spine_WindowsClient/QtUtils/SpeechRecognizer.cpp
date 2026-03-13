#include "SpeechRecognizer.h"
#include <QDebug>
#include <QJsonArray>
#include <QJsonValue>

SpeechRecognizer::SpeechRecognizer(QObject* parent)
    : QObject(parent)
    , m_model(nullptr)
    , m_spkModel(nullptr)
    , m_recognizer(nullptr)
    , m_initialized(false)
    , m_recognizing(false)
    , m_sampleRate(16000.0f)
    , m_maxAlternatives(0)
    , m_wordsEnabled(false)
    , m_partialWordsEnabled(false)
    , m_nlsmlEnabled(false)
{
    qDebug().noquote() << FINE_PR << "[Vosk]SpeechRecognizer created!";
}

SpeechRecognizer::~SpeechRecognizer()
{
    shutdown();
}

bool SpeechRecognizer::initialize(const QString& modelPath, float sampleRate)
{
    QMutexLocker locker(&m_mutex);

    if (m_initialized) {
        qWarning().noquote() << ERROR_PR << "[Vosk]Recognizer already initialized";
        return true;
    }

    // 加载模型
    m_model = vosk_model_new(modelPath.toUtf8().constData());
    if (!m_model) {
        emit errorOccurred("Failed to load model from: " + modelPath);
        return false;
    }

    // 创建识别器
    m_recognizer = vosk_recognizer_new(m_model, sampleRate);
    if (!m_recognizer) {
        vosk_model_free(m_model);
        m_model = nullptr;
        emit errorOccurred("Failed to create recognizer");
        return false;
    }

    m_sampleRate = sampleRate;
    m_initialized = true;

    qDebug().noquote() << FINE_PR << "[Vosk]Vosk recognizer initialized successfully with model:" << modelPath;
    emit initialized();

    return true;
}

bool SpeechRecognizer::initializeWithSpeaker(const QString& modelPath, const QString& spkModelPath, float sampleRate)
{
    QMutexLocker locker(&m_mutex);

    if (m_initialized) {
        qWarning().noquote() << ERROR_PR << "[Vosk]Recognizer already initialized";
        return true;
    }

    // 加载主模型
    m_model = vosk_model_new(modelPath.toUtf8().constData());
    if (!m_model) {
        emit errorOccurred("Failed to load model from: " + modelPath);
        return false;
    }

    // 加载说话人模型
    m_spkModel = vosk_spk_model_new(spkModelPath.toUtf8().constData());
    if (!m_spkModel) {
        vosk_model_free(m_model);
        m_model = nullptr;
        emit errorOccurred("Failed to load speaker model from: " + spkModelPath);
        return false;
    }

    // 创建带说话人识别的识别器
    m_recognizer = vosk_recognizer_new_spk(m_model, sampleRate, m_spkModel);
    if (!m_recognizer) {
        vosk_model_free(m_model);
        vosk_spk_model_free(m_spkModel);
        m_model = nullptr;
        m_spkModel = nullptr;
        emit errorOccurred("Failed to create recognizer with speaker model");
        return false;
    }

    m_sampleRate = sampleRate;
    m_initialized = true;

    qDebug().noquote() << FINE_PR << "[Vosk]Vosk recognizer with speaker model initialized successfully";
    emit initialized();

    return true;
}

bool SpeechRecognizer::initializeWithGrammar(const QString& modelPath, const QString& grammar, float sampleRate)
{
    QMutexLocker locker(&m_mutex);

    if (m_initialized) {
        qWarning() << "Recognizer already initialized";
        return true;
    }

    // 加载模型
    m_model = vosk_model_new(modelPath.toUtf8().constData());
    if (!m_model) {
        emit errorOccurred("Failed to load model from: " + modelPath);
        return false;
    }

    // 创建带语法的识别器
    m_recognizer = vosk_recognizer_new_grm(m_model, sampleRate, grammar.toUtf8().constData());
    if (!m_recognizer) {
        vosk_model_free(m_model);
        m_model = nullptr;
        emit errorOccurred("Failed to create recognizer with grammar");
        return false;
    }

    m_sampleRate = sampleRate;
    m_grammar = grammar;
    m_initialized = true;

    qDebug().noquote() << FINE_PR << "[Vosk]Vosk recognizer with grammar initialized successfully";
    emit initialized();

    return true;
}

void SpeechRecognizer::shutdown()
{
    QMutexLocker locker(&m_mutex);

    if (m_recognizer) {
        vosk_recognizer_free(m_recognizer);
        m_recognizer = nullptr;
    }

    if (m_spkModel) {
        vosk_spk_model_free(m_spkModel);
        m_spkModel = nullptr;
    }

    if (m_model) {
        vosk_model_free(m_model);
        m_model = nullptr;
    }

    m_initialized = false;
    m_recognizing = false;

    qDebug().noquote() << FINE_PR << "[Vosk]SpeechRecognizer shutdown complete";
}

void SpeechRecognizer::startRecognition()
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    if (!m_recognizing) {
        vosk_recognizer_reset(m_recognizer);
        m_recognizing = true;
        clearResults();
        emit recognitionStarted();
        qDebug().noquote() << FINE_PR << "[Vosk]Recognition started";
    }
}

void SpeechRecognizer::stopRecognition()
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    if (m_recognizing) {
        m_recognizing = false;
        emit recognitionStopped();
        qDebug().noquote() << FINE_PR << "[Vosk]Recognition stopped";
    }
}

void SpeechRecognizer::reset()
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    vosk_recognizer_reset(m_recognizer);
    clearResults();
    qDebug().noquote() << FINE_PR << "[Vosk]Recognizer reset";
}

void SpeechRecognizer::setMaxAlternatives(int maxAlternatives)
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    m_maxAlternatives = maxAlternatives;
    vosk_recognizer_set_max_alternatives(m_recognizer, maxAlternatives);
    qDebug().noquote() << FINE_PR << "[Vosk]Max alternatives set to:" << maxAlternatives;
}

void SpeechRecognizer::enableWords(bool enable)
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    m_wordsEnabled = enable;
    vosk_recognizer_set_words(m_recognizer, enable ? 1 : 0);
    qDebug().noquote() << FINE_PR << "[Vosk]Words enabled:" << enable;
}

void SpeechRecognizer::enablePartialWords(bool enable)
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    m_partialWordsEnabled = enable;
    vosk_recognizer_set_partial_words(m_recognizer, enable ? 1 : 0);
    qDebug().noquote() << FINE_PR << "[Vosk]Partial words enabled:" << enable;
}

void SpeechRecognizer::enableNLSML(bool enable)
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    m_nlsmlEnabled = enable;
    vosk_recognizer_set_nlsml(m_recognizer, enable ? 1 : 0);
    qDebug().noquote() << FINE_PR << "[Vosk]NLSML enabled:" << enable;
}

void SpeechRecognizer::setGrammar(const QString& grammar)
{
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);
    m_grammar = grammar;
    vosk_recognizer_set_grm(m_recognizer, grammar.toUtf8().constData());
    qDebug().noquote() << FINE_PR << "[Vosk]Grammar updated";
}

bool SpeechRecognizer::acceptWaveform(const QByteArray& audioData)
{
    if (!checkInitialized() || !m_recognizing) {
        return false;
    }

    QMutexLocker locker(&m_mutex);

    int result = vosk_recognizer_accept_waveform(
        m_recognizer,
        audioData.constData(),
        audioData.size()
    );

    if (result < 0) {
        emit errorOccurred("Error processing waveform");
        return false;
    }

    // 检查是否有最终结果
    if (result == 1) {
        RecognitionResult finalResult = getResult();
        if (!finalResult.text.isEmpty()) {
            emit resultReady(finalResult);
        }
    }

    // 获取部分结果
    RecognitionResult partialResult = getPartialResult();
    if (!partialResult.partialText.isEmpty()) {
        emit partialResultReady(partialResult);
    }

    return true;
}

bool SpeechRecognizer::acceptWaveform(const short* audioData, int length)
{
    if (!checkInitialized() || !m_recognizing) {
        return false;
    }

    QMutexLocker locker(&m_mutex);

    int result = vosk_recognizer_accept_waveform_s(m_recognizer, audioData, length);

    if (result < 0) {
        emit errorOccurred("Error processing waveform (short)");
        return false;
    }

    if (result == 1) {
        RecognitionResult finalResult = getResult();
        if (!finalResult.text.isEmpty()) {
            emit resultReady(finalResult);
        }
    }

    RecognitionResult partialResult = getPartialResult();
    if (!partialResult.partialText.isEmpty()) {
        emit partialResultReady(partialResult);
    }

    return true;
}

RecognitionResult SpeechRecognizer::getResult()
{
    RecognitionResult result;

    if (!checkInitialized()) {
        return result;
    }

    QMutexLocker locker(&m_mutex);

    const char* jsonResult = vosk_recognizer_result(m_recognizer);
    if (jsonResult) {
        result = parseResult(jsonResult);
        result.isFinal = true;
        m_lastResult = result;
    }

    return result;
}

RecognitionResult SpeechRecognizer::getPartialResult()
{
    RecognitionResult result;

    if (!checkInitialized()) {
        return result;
    }

    QMutexLocker locker(&m_mutex);

    const char* jsonResult = vosk_recognizer_partial_result(m_recognizer);
    if (jsonResult) {
        result = parseResult(jsonResult);
        result.isFinal = false;
        m_lastPartialResult = result;
    }

    return result;
}

RecognitionResult SpeechRecognizer::getFinalResult()
{
    RecognitionResult result;

    if (!checkInitialized()) {
        return result;
    }

    QMutexLocker locker(&m_mutex);

    const char* jsonResult = vosk_recognizer_final_result(m_recognizer);
    if (jsonResult) {
        result = parseResult(jsonResult);
        result.isFinal = true;
        m_lastResult = result;
    }

    return result;
}

RecognitionResult SpeechRecognizer::parseResult(const char* jsonResult)
{
    RecognitionResult result;

    if (!jsonResult) {
        return result;
    }

    QString jsonString = QString::fromUtf8(jsonResult);
    result.fullJson = QJsonDocument::fromJson(jsonString.toUtf8()).object();

    // 解析文本
    if (result.fullJson.contains("text")) {
        result.text = result.fullJson["text"].toString();
    }

    if (result.fullJson.contains("partial")) {
        result.partialText = result.fullJson["partial"].toString();
    }

    // 解析置信度（如果有）
    if (result.fullJson.contains("confidence")) {
        result.confidence = result.fullJson["confidence"].toDouble();
    }
    else if (result.fullJson.contains("alternatives")) {
        QJsonArray alternatives = result.fullJson["alternatives"].toArray();
        if (!alternatives.isEmpty()) {
            QJsonObject first = alternatives.first().toObject();
            if (first.contains("confidence")) {
                result.confidence = first["confidence"].toDouble();
            }
        }
    }

    return result;
}

void SpeechRecognizer::clearResults()
{
    m_lastResult = RecognitionResult();
    m_lastPartialResult = RecognitionResult();
}

bool SpeechRecognizer::checkInitialized() const
{
    if (!m_initialized || !m_recognizer) {
        qWarning().noquote() << ERROR_PR << "[Vosk]SpeechRecognizer not initialized";
        return false;
    }
    return true;
}

// 静态成员函数实现
QString SpeechRecognizer::version()
{
    // Vosk 没有直接提供版本获取函数，返回固定字符串
    return "0.3.45"; // 常见版本号，可以根据实际情况调整
}

void SpeechRecognizer::setLogLevel(int level)
{
    vosk_set_log_level(level);
}

void SpeechRecognizer::initGPU()
{
    vosk_gpu_init();
}

void SpeechRecognizer::initGPUThread()
{
    vosk_gpu_thread_init();
}

void SpeechRecognizer::processPendingResults()
{
    // 这个函数可以在单独的线程中调用，处理待处理的结果
    if (!checkInitialized()) return;

    QMutexLocker locker(&m_mutex);

    // 检查是否有新的最终结果
    const char* jsonResult = vosk_recognizer_result(m_recognizer);
    if (jsonResult) {
        RecognitionResult result = parseResult(jsonResult);
        result.isFinal = true;
        emit resultReady(result);
    }

    // 检查部分结果
    const char* partialJson = vosk_recognizer_partial_result(m_recognizer);
    if (partialJson) {
        RecognitionResult result = parseResult(partialJson);
        result.isFinal = false;
        emit partialResultReady(result);
    }
}