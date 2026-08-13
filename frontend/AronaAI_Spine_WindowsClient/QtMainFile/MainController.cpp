/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

#include "MainController.h"
#include <QTimer>

MainController::MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, TencentSpeechRecognizer* speechRecognizer, WebSocketController* webSocketController, UserInputWidget* userInputWidget)
    : m_mainWidget(mainWidget)
    , m_ttsManager(ttsManager)
    , m_audioRecorder(audioRecorder)
    , m_tencentRecognizer(speechRecognizer)
    , m_webSocketController(webSocketController)
    , m_userInputWidget(userInputWidget)
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
            if (success) {
                FINE_DEBUG_OUTPUT("[TTS Operation]Model set: " + QString(success?"true":"false")
                    + ", Message: " + message 
                    + "(" + QString::number(m_modelsLoaded) + "/" + QString::number(TOTAL_MODELS) + ")");
            }
            else {
                ERROR_DEBUG_OUTPUT("[TTS Operation]Model set: " + QString(success?"true":"false")
                    + ", Message: " + message 
					+ "(" + QString::number(m_modelsLoaded) + "/" + QString::number(TOTAL_MODELS) + ")");
            }

            // 当两个模型都加载完成时退出事件循环
            if (m_modelsLoaded >= TOTAL_MODELS) {
                loop.quit();
            }
        });
    // 启动事件循环，等待模型设置完成
    if (m_modelsLoaded < TOTAL_MODELS) {
        loop.exec();
    }
    FINE_DEBUG_OUTPUT("[TTS Operation]All models loaded!");

    // 设置信号与槽
    connect(m_ttsManager, &TTSManager::ttsFinished, this, &MainController::onTTSFinished);
    connect(m_ttsManager, &TTSManager::ttsError, this, &MainController::onTTSError);

    // 连接音频录制对象信号
    connect(m_audioRecorder, &AudioRecorder::errorOccurred,
        this, &MainController::onAudioError);

    // 连接腾讯云语音识别信号（对象由 main 传入）
    if (m_tencentRecognizer) {
        m_tencentRecognizer->setParent(this);
    }
    connect(m_tencentRecognizer, &TencentSpeechRecognizer::errorOccurred,
        this, &MainController::onRecognizeError);
    connect(m_tencentRecognizer, &TencentSpeechRecognizer::recognizeFinished,
		this, &MainController::onRecognizeFinished);

    // 设置你的腾讯云密钥 (请务必从安全的地方读取，不要硬编码)
    m_tencentRecognizer->setCredentials(GET_STRING_FROM_JSON(_global_config, "tencent_speech_recognizer", "secret_id"), GET_STRING_FROM_JSON(_global_config, "tencent_speech_recognizer", "secret_key"));

    // 与服务端建立WebSocket连接
    // 连接 WebSocket 信号到 MainController 槽函数
    connect(m_webSocketController, &WebSocketController::connected,
        this, &MainController::onWebSocketConnected);
    connect(m_webSocketController, &WebSocketController::chatResponseReceived,
        this, &MainController::onWebSocketChatResponse);
    connect(m_webSocketController, &WebSocketController::errorOccurred,
        this, &MainController::onWebSocketError);
    connect(m_webSocketController, &WebSocketController::connectionStateChanged,
        this, &MainController::onWebSocketStateChanged);

    // 开始连接服务端
    m_webSocketController->connectToServer();
    FINE_DEBUG_OUTPUT("[WebSocket] Connecting to: " + GET_STRING_FROM_JSON(_global_config, "aronalm", "websocket_url"));

    // 连接用户文本输入提交信号
    if (m_userInputWidget) {
        connect(m_userInputWidget, &UserInputWidget::textSubmitted,
            this, &MainController::processInputText);
    }

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
    holdOrPresentOutput(audioData, mediaType, false);
}

void MainController::presentOutput(const QByteArray& audioData, const QString& mediaType)
{
    Q_UNUSED(mediaType);
    // 播放音频
    m_ttsManager->playAudio(audioData);
    // 显示文字
    m_mainWidget->showOutputText(m_currentText);
    if (m_measuringUserTurn) {
        FINE_DEBUG_OUTPUT(QString("[Latency] User send to text on screen: %1 ms")
            .arg(m_userTurnTimer.elapsed()));
        m_measuringUserTurn = false;
    }
    // 计算播放时长
    int duration = m_currentText.size() * 100; // 每个字符100ms
    duration = (int)(1000 * (m_ttsManager->getWavDuration(audioData)));   // 按照实际音频时长设置，单位为毫秒
    // 启动动画：表情层(1) + 语言口型层(2)
    const QString expressionAnim = AronaEmotion::toAnimationName(m_currentEmotion);
    m_mainWidget->setAnimation(expressionAnim, 1, true);   // 表情层
    m_mainWidget->setAnimation("Arona_Work_In_1_CN", 2, true);   // 语言口型层
    // 在duration之后清除显示的文字，停止动画
    QTimer::singleShot(duration, this, [this]() {
        m_mainWidget->hideOutputText();
		m_mainWidget->clearAnimation(2, 0.2f);   // 停止语言口型层
		m_mainWidget->clearAnimation(1, 0.2f);   // 停止表情层
        });
}

void MainController::onTTSError(const QString& errorString)
{
    ERROR_DEBUG_OUTPUT("[TTS Operation]TTS error: " + errorString);

    if (m_currentText.isEmpty()) {
        m_measuringUserTurn = false;
        if (m_awaitingStartupWelcome) {
            m_awaitingStartupWelcome = false;
            if (m_splashActive) {
                emit welcomePlaybackReady();
            }
        }
        return;
    }

    holdOrPresentOutput(QByteArray(), QString(), true);
}

void MainController::presentOutputError()
{
    // 语音失败时仍展示字幕与表情，避免交互卡住
    m_mainWidget->showOutputText(m_currentText);
    if (m_measuringUserTurn) {
        FINE_DEBUG_OUTPUT(QString("[Latency] User send to text on screen: %1 ms")
            .arg(m_userTurnTimer.elapsed()));
        m_measuringUserTurn = false;
    }
    const QString expressionAnim = AronaEmotion::toAnimationName(m_currentEmotion);
    m_mainWidget->setAnimation(expressionAnim, 1, true);
    int duration = qMax(1500, m_currentText.size() * 100);
    QTimer::singleShot(duration, this, [this]() {
        m_mainWidget->hideOutputText();
        m_mainWidget->clearAnimation(1, 0.2f);
        });
}

void MainController::holdOrPresentOutput(const QByteArray& audioData, const QString& mediaType, bool isError)
{
    if (m_awaitingStartupWelcome) {
        m_awaitingStartupWelcome = false;
        if (m_splashActive) {
            m_hasPendingOutput = true;
            m_pendingIsError = isError;
            m_pendingAudio = audioData;
            m_pendingMediaType = mediaType;
            FINE_DEBUG_OUTPUT(QString("[Main Controller] Welcome TTS %1, waiting for splash close")
                .arg(isError ? "error" : "ready"));
            emit welcomePlaybackReady();
            return;
        }
    }

    if (isError) {
        presentOutputError();
    } else {
        presentOutput(audioData, mediaType);
    }
}

void MainController::onSplashClosed()
{
    if (!m_splashActive) {
        return;
    }
    m_splashActive = false;
    FINE_DEBUG_OUTPUT("[Main Controller] Splash closed");
    if (!m_hasPendingOutput) {
        return;
    }
    m_hasPendingOutput = false;
    if (m_pendingIsError) {
        presentOutputError();
    } else {
        presentOutput(m_pendingAudio, m_pendingMediaType);
    }
    m_pendingAudio.clear();
    m_pendingMediaType.clear();
}

void MainController::dismissSplashOnUnrecoverableError()
{
    if (!m_splashActive || !m_awaitingStartupWelcome) {
        return;
    }
    m_awaitingStartupWelcome = false;
    FINE_DEBUG_OUTPUT("[Main Controller] Unrecoverable WS error, dismissing splash");
    emit welcomePlaybackReady();
}

void MainController::startAudioProcessing()
{
    if (m_audioRecorder->startRecording()) {
        FINE_DEBUG_OUTPUT("[Audio Input Processing]Recording");
    }
    else {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Failed to start recording");
    }
}

// 停止录音识别
void MainController::stopAudioProcessing()
{
    // 停止录制并获取音频数据
    QByteArray audioData = m_audioRecorder->stopRecording();
    FINE_DEBUG_OUTPUT("[Audio Input Processing]Recognizing...");

    // 识别结果
    QString input_text;
    if (!audioData.isEmpty()) {
        // 直接调用腾讯云的识别，结果会通过 recognizeFinished 信号返回
        m_tencentRecognizer->recognize(audioData);
    }
    else {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Failed to capture audio!");
        return;
    }
    FINE_DEBUG_OUTPUT("[Audio Input Processing]Audio processing program is ready!");
}

void MainController::toggleMouseTransparent()
{
    bool nextState = !m_mainWidget->isMouseTransparent();
    m_mainWidget->setMouseTransparent(nextState);
    FINE_DEBUG_OUTPUT(QString("[Main Controller] Mouse transparent toggled to: %1")
        .arg(nextState ? "true" : "false"));
}

void MainController::showUserInput()
{
    if (!m_userInputWidget) {
        ERROR_DEBUG_OUTPUT("[Main Controller] UserInputWidget is null");
        return;
    }
    m_userInputWidget->showForInput();
    FINE_DEBUG_OUTPUT("[Main Controller] User input widget shown");
}

void MainController::onAudioError(const QString& error)
{
    ERROR_DEBUG_OUTPUT("[Audio Input Processing]Audio error!");
}

void MainController::onRecognizeError(const QString& error)
{
    ERROR_DEBUG_OUTPUT("[Audio Input Processing]Recognize error!");
}

void MainController::onRecognizeFinished(const QString& text)
{
    const QString trimmed = text.trimmed();
    FINE_DEBUG_OUTPUT("[Audio Input Processing]Recognize finished! Result: " + trimmed);
    // Drop ASR error strings that were historically mis-emitted as success
    if (trimmed.isEmpty()
        || trimmed.contains(QStringLiteral("[Tencent Speech Recognizer]"))
        || trimmed.contains(QStringLiteral("Didnt recognize"), Qt::CaseInsensitive)
        || trimmed.contains(QStringLiteral("Didn't recognize"), Qt::CaseInsensitive)) {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Ignoring unusable ASR text, not sending chat");
        return;
    }
    processInputText(trimmed);
}

void MainController::processInputText(const QString& text)
{
    const QString trimmed = text.trimmed();
    FINE_DEBUG_OUTPUT("[Main Controller] Processing input: " + trimmed);

    if (trimmed.isEmpty()) {
        ERROR_DEBUG_OUTPUT("[Main Controller] Empty input, skip send");
        return;
    }

    // 检查 WebSocket 是否已连接
    if (!m_webSocketController->isConnected()) {
        // 如果未连接，给出本地提示
        executeOutput("AI服务未连接，请检查网络后重试");
        ERROR_DEBUG_OUTPUT("[Main Controller] WebSocket not connected, cannot process input");
        return;
    }

    // 检查是否正在等待上一次回复
    if (m_waitingForAIResponse) {
        FINE_DEBUG_OUTPUT("正在处理上一条消息，请稍候");
        FINE_DEBUG_OUTPUT("[Main Controller] Waiting for previous AI response");
        return;
    }

    // 标记正在等待AI回复
    m_waitingForAIResponse = true;

    // 给用户一个等待提示
    FINE_DEBUG_OUTPUT("[Main Controller] 、Generating responce...");

    // 发送消息给AI服务端
    // 可以从配置中读取是否使用缓存、RAG、记忆等功能
    bool useCache = GET_BOOL_FROM_JSON(_global_config, "aronalm", "use_cache");
    bool useRag = GET_BOOL_FROM_JSON(_global_config, "aronalm", "use_rag");
    bool useMemory = GET_BOOL_FROM_JSON(_global_config, "aronalm", "use_memory");

    m_backendTimer.restart();
    m_userTurnTimer.restart();
    m_measuringUserTurn = true;

    m_webSocketController->sendChatMessage(trimmed, useCache, useRag, useMemory);

    FINE_DEBUG_OUTPUT("[Main Controller] Sent to AI service: " + trimmed.left(50) + "...");
}

void MainController::onWebSocketConnected(const QString& sessionId)
{
    FINE_DEBUG_OUTPUT("[WebSocket] Connected! Session ID: " + sessionId);
    // 连接成功后可以发送欢迎消息或其他初始化操作
}

void MainController::onWebSocketChatResponse(const QString& content, bool fromCache, const QString& contextUsed, double latency, const QString& emotion)
{
    FINE_DEBUG_OUTPUT(QString("[Latency] Backend RTT: %1 ms (server_reported: %2s)")
        .arg(m_backendTimer.elapsed())
        .arg(latency, 0, 'f', 2));
    FINE_DEBUG_OUTPUT("[WebSocket] Received AI response: " + content.left(50) + "...");
    FINE_DEBUG_OUTPUT(QString("[WebSocket] Cache: %1, Context: %2, Latency: %3s, Emotion: %4")
        .arg(fromCache ? "yes" : "no")
        .arg(contextUsed)
        .arg(latency)
        .arg(emotion));
    if (m_awaitingStartupWelcome && contextUsed.contains(QStringLiteral("welcome"))) {
        FINE_DEBUG_OUTPUT("[WebSocket] Startup welcome chat_response received");
    }

    // 重置等待状态
    m_waitingForAIResponse = false;
    m_currentEmotion = emotion.isEmpty() ? QStringLiteral("normal") : emotion;

    // 通过TTS播放AI回复
    executeOutput(content);
}

void MainController::onWebSocketError(WebSocketController::ErrorCode code, const QString& message)
{
    ERROR_DEBUG_OUTPUT(QString("[WebSocket] Error (code: %1): %2").arg(static_cast<int>(code)).arg(message));

    if (m_waitingForAIResponse) {
        FINE_DEBUG_OUTPUT(QString("[Latency] Backend RTT (failed): %1 ms")
            .arg(m_backendTimer.elapsed()));
        m_measuringUserTurn = false;
    }

    // 重置等待状态
    m_waitingForAIResponse = false;

    // 根据错误类型给出不同的用户提示
    QString userMessage;
    switch (code) {
    case WebSocketController::ErrorCode::ConnectionRefused:
        userMessage = "无法连接到AI服务，请检查服务是否启动";
        break;
    case WebSocketController::ErrorCode::ConnectionTimeout:
        userMessage = "连接AI服务超时，请检查网络";
        break;
    case WebSocketController::ErrorCode::HeartbeatTimeout:
        userMessage = "与AI服务连接中断，正在尝试重连";
        break;
    case WebSocketController::ErrorCode::ReconnectFailed:
        userMessage = "无法重新连接到AI服务";
        break;
    case WebSocketController::ErrorCode::NetworkError:
        userMessage = "无法连接到AI服务，请检查服务是否启动";
        break;
    default:
        userMessage = "AI服务出现错误: " + message;
        break;
    }

    if (m_splashActive) {
        if (m_awaitingStartupWelcome) {
            m_currentText = userMessage;
            m_currentEmotion = QStringLiteral("normal");
            m_hasPendingOutput = true;
            m_pendingIsError = true;
            dismissSplashOnUnrecoverableError();
        }
        return;
    }

    // 显示文字
    m_mainWidget->showOutputText(userMessage);
    // 计算播放时长
    int duration = userMessage.size() * 100; // 每个字符100ms
    // 在duration之后清除显示的文字，停止动画
    QTimer::singleShot(duration, this, [this]() {
        m_mainWidget->hideOutputText();
        });
}

void MainController::onWebSocketStateChanged(WebSocketController::ConnectionState state)
{
    QString stateStr;
    switch (state) {
    case WebSocketController::ConnectionState::Disconnected:
        stateStr = "Disconnected";
        break;
    case WebSocketController::ConnectionState::Connecting:
        stateStr = "Connecting";
        break;
    case WebSocketController::ConnectionState::Connected:
        stateStr = "Connected";
        break;
    case WebSocketController::ConnectionState::Reconnecting:
        stateStr = "Reconnecting";
        break;
    }
    FINE_DEBUG_OUTPUT("[WebSocket] State changed: " + stateStr);

    // 如果连接断开，更新UI状态
    if (state == WebSocketController::ConnectionState::Disconnected) {
        if (m_waitingForAIResponse) {
            FINE_DEBUG_OUTPUT(QString("[Latency] Backend RTT (failed): %1 ms")
                .arg(m_backendTimer.elapsed()));
            m_measuringUserTurn = false;
        }
        m_waitingForAIResponse = false;
    }
}
