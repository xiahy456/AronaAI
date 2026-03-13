#include "MainController.h"

MainController::MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, SpeechRecognizer* speechRecognizer)
    : m_mainWidget(mainWidget)
    , m_ttsManager(ttsManager)
    , m_audioRecorder(audioRecorder)
    , m_speechRecognizer(speechRecognizer)
{
    // 进行TTS初始化
    // 构建TTS请求参数
    ttsRequestParams.text = "";  // 要合成的文本
    ttsRequestParams.textLang = GET_STRING_FROM_JSON(_global_config, "tts", "text_lang");    // 文本语言
    ttsRequestParams.refAudioPath = GET_STRING_FROM_JSON(_global_config, "tts", "ref_audio_path");  // 参考音频路径
    ttsRequestParams.auxRefAudioPaths;   // 辅助参考音频路径
    ttsRequestParams.promptText = GET_STRING_FROM_JSON(_global_config, "tts", "prompt_text");    // 提示文本
    ttsRequestParams.promptLang = GET_STRING_FROM_JSON(_global_config, "tts", "prompt_lang");  // 提示文本语言
    ttsRequestParams.topK = GET_INT_FROM_JSON(_global_config, "tts", "top_k");   // top k采样
    ttsRequestParams.topP = GET_DOUBLE_FROM_JSON(_global_config, "tts", "top_p");  // top p采样
    ttsRequestParams.temperature = GET_DOUBLE_FROM_JSON(_global_config, "tts", "temperature");   // 温度参数
    ttsRequestParams.textSplitMethod = GET_STRING_FROM_JSON(_global_config, "tts", "text_split_method");   // 文本分割方法
    ttsRequestParams.batchSize = GET_INT_FROM_JSON(_global_config, "tts", "batch_size");  // 批处理大小
    ttsRequestParams.batchThreshold = GET_DOUBLE_FROM_JSON(_global_config, "tts", "batch_threshold");   // 批处理阈值
    ttsRequestParams.splitBucket = GET_BOOL_FROM_JSON(_global_config, "tts", "split_bucket");    // 是否分割桶
    ttsRequestParams.speedFactor = GET_DOUBLE_FROM_JSON(_global_config, "tts", "speed_factor");   // 语速因子
    ttsRequestParams.fragmentInterval = GET_DOUBLE_FROM_JSON(_global_config, "tts", "fragment_interval");  // 片段间隔
    ttsRequestParams.seed = GET_INT_FROM_JSON(_global_config, "tts", "seed");  // 随机种子
    ttsRequestParams.streamingMode = GET_BOOL_FROM_JSON(_global_config, "tts", "streaming_mode"); // 流式模式
    ttsRequestParams.parallelInfer = GET_BOOL_FROM_JSON(_global_config, "tts", "parallel_infer");  // 并行推理
    ttsRequestParams.repetitionPenalty = GET_DOUBLE_FROM_JSON(_global_config, "tts", "repetition_penalty");    // 重复惩罚
    ttsRequestParams.sampleSteps = GET_INT_FROM_JSON(_global_config, "tts", "sample_steps");   // 采样步数
    ttsRequestParams.superSampling = GET_BOOL_FROM_JSON(_global_config, "tts", "super_sampling"); // 超采样
    ttsRequestParams.mediaType = "wav";  // 媒体类型

    int m_modelsLoaded = 0; // 已加载的模型计数器
    const int TOTAL_MODELS = 2;  // 总共需要加载的模型数

    // 为TTS设置GPT模型
    m_ttsManager->setGPTWeights(GET_STRING_FROM_JSON(_global_config, "tts", "gpt_path"));

    // 为TTS设置SoVITS模型
    m_ttsManager->setSovitsWeights(GET_STRING_FROM_JSON(_global_config, "tts", "sovits_path"));

    // 连接信号，使用计数器判断两个模型都加载完成
    QEventLoop loop; // 创建事件循环
    connect(m_ttsManager, &TTSManager::modelSwitched, this,
        [&](bool success, const QString& message) {
            m_modelsLoaded++;
            qDebug().noquote() << FINE_PR << "[TTS Operation]Model set: " << success
                << ", Message: " << message
                << "(" << m_modelsLoaded << "/" << TOTAL_MODELS << ")";

            // 当两个模型都加载完成时退出事件循环
            if (m_modelsLoaded >= TOTAL_MODELS) {
                loop.quit();
            }
        });
    // 启动事件循环，等待模型设置完成
    if (m_modelsLoaded < TOTAL_MODELS) {
        loop.exec();
    }
    qDebug().noquote() << FINE_PR << "[TTS Operation]All models loaded!";

    // 设置信号与槽
    connect(m_ttsManager, &TTSManager::ttsFinished, this, &MainController::onTTSFinished);

    // 输出一段文本，验证TTS功能是否正常
    executeOutput(GET_STRING_FROM_JSON(_global_dict, "formed_text", "connected_to_os_operator"));

    // 连接录音器AudioRecorder信号
    connect(m_audioRecorder, &AudioRecorder::recordingStarted, this, &MainController::onRecordingStarted);
    connect(m_audioRecorder, &AudioRecorder::recordingStopped, this, &MainController::onRecordingStopped);
    connect(m_audioRecorder, &AudioRecorder::audioDataReady, this, &MainController::onAudioDataReady);
    connect(m_audioRecorder, &AudioRecorder::audioLevelChanged, this, &MainController::onAudioLevelChanged);
    connect(m_audioRecorder, &AudioRecorder::recordingError, this, &MainController::onError);

    // 连接识别器SpeechRecognizer信号
    connect(m_speechRecognizer, &SpeechRecognizer::resultReady, this, &MainController::onResultReady);
    connect(m_speechRecognizer, &SpeechRecognizer::partialResultReady, this, &MainController::onPartialResultReady);
    connect(m_speechRecognizer, &SpeechRecognizer::errorOccurred, this, &MainController::onError);

    // 初始化 Vosk
    if (!initializeVosk()) qWarning().noquote() << ERROR_PR << "[Vosk]Initiallized failed! Please check the model path";

}

MainController::~MainController()
{

}

void MainController::executeOutput(const QString& text)
{
    // 将文本添加进TTS请求参数中
    ttsRequestParams.text = text;
    // 保存该文本
    m_currentText = text;
    // 调用TTSManager进行文本到语音的转换
    m_ttsManager->requestTTSPost(ttsRequestParams);

}

void MainController::onTTSFinished(const QByteArray& audioData, const QString& mediaType)
{
    // 播放音频
    m_ttsManager->playAudio(audioData);
    // 显示文字
    m_mainWidget->showOutputText(m_currentText);
    // 计算播放时长
    int duration = m_currentText.size() * 100; // 简单估算：每个字符100ms
    duration = (int)(1000 * (m_ttsManager->getWavDuration(audioData)));   // 按照实际音频时长设置，单位为毫秒
    // 启动动画
    m_mainWidget->setAnimation("25", 1, true);   // 表情层
    m_mainWidget->setAnimation("Arona_Work_In_1_CN", 2, true);   // 语言层
    // 在duration之后清除显示的文字，停止动画
    QTimer::singleShot(duration, this, [this]() {
        m_mainWidget->hideOutputText();
        m_mainWidget->setAnimation("Idle_01", 2, true);
        m_mainWidget->setAnimation("Idle_01", 1, true);
        });
}

bool MainController::initializeVosk()
{
    // 设置 Vosk 日志级别
    SpeechRecognizer::setLogLevel(0);

    // 启用 GPU 加速
    SpeechRecognizer::initGPU();

    // 模型路径
    QString modelPath = GET_STRING_FROM_JSON(_global_config, "vosk", "model_path");

    // 初始化识别器
    bool success = m_speechRecognizer->initialize(modelPath, 16000.0f);

    if (success) {
        // 配置识别器选项
        m_speechRecognizer->enableWords(true);           // 启用单词级结果
        m_speechRecognizer->enablePartialWords(true);    // 启用部分单词结果
        m_speechRecognizer->setMaxAlternatives(3);       // 设置最多3个备选结果

        qDebug().noquote() << FINE_PR << "[Vosk]Vosk initiallized!";
    }

    return success;
}
bool MainController::startAudioProcessing()
{
    if (!m_speechRecognizer->isInitialized()) {
        qWarning().noquote() << ERROR_PR << "[Audio Input Processing]Recognizer not initialized";
        return false;
    }

    m_speechRecognizer->startRecognition();
    return m_audioRecorder->startRecording();
}

// 停止录音识别
void MainController::stopAudioProcessing()
{
    m_audioRecorder->stopRecording();
    m_speechRecognizer->stopRecognition();
}

// 处理音频文件（离线识别）
bool MainController::processAudioFile(const QString& filePath)
{
    QFile file(filePath);
    if (!file.open(QIODevice::ReadOnly)) {
        qWarning().noquote() << ERROR_PR << "[Audio Input Processing]Cannot open file:" << filePath;
        return false;
    }

    QByteArray audioData = file.readAll();
    file.close();

    m_speechRecognizer->startRecognition();

    // 一次性发送所有音频数据
    m_speechRecognizer->acceptWaveform(audioData);

    // 获取最终结果
    RecognitionResult result = m_speechRecognizer->getFinalResult();
    qDebug().noquote() << ERROR_PR << "[Audio Input Processing]File recognition result:" << result.text;

    m_speechRecognizer->stopRecognition();

    return true;
}

// 获取识别结果（同步方式）
QString MainController::recognizeSync(int durationMs)
{
    QString result;

    // 连接临时信号处理器
    QEventLoop loop;
    QTimer::singleShot(durationMs, &loop, &QEventLoop::quit);

    connect(m_speechRecognizer, &SpeechRecognizer::resultReady,
        &loop, [&](const RecognitionResult& res) {
            result = res.text;
            loop.quit();
        });

    // 开始识别
    startAudioProcessing();

    // 等待指定时间或得到结果
    loop.exec();

    // 停止识别
    stopAudioProcessing();

    return result;
}

void MainController::onAudioDataReady(const QByteArray& data)
{
    m_speechRecognizer->acceptWaveform(data);
}

void MainController::onRecordingStarted()
{
    qDebug().noquote() << FINE_PR << "[Audio Input Processing]Recording started...";
}

void MainController::onRecordingStopped()
{
    qDebug().noquote() << FINE_PR << "[Audio Input Processing]Recording stopped.";
}

void MainController::onResultReady(const RecognitionResult& result)
{
    qDebug().noquote() << FINE_PR << "[Audio Input Processing]Final result:" << result.text;
    emit resultAvailable(result.text);
}

void MainController::onPartialResultReady(const RecognitionResult& result)
{
    qDebug().noquote() << FINE_PR << "[Audio Input Processing]Partial:" << result.partialText;
    emit partialResultAvailable(result.partialText);
}

void MainController::onError(const QString& error)
{
    qWarning().noquote() << ERROR_PR << "[Audio Input Processing]Error:" << error;
}

void MainController::onAudioLevelChanged(int level)
{

}
