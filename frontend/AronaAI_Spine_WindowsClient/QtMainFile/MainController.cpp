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

    connect(m_ttsManager, &TTSManager::ttsFinished, this, &MainController::onTTSFinished);
    connect(m_ttsManager, &TTSManager::ttsError, this, &MainController::onTTSError);

    m_ttsWeightTimer.start();
    connect(m_ttsManager, &TTSManager::modelSwitched, this,
        [this](bool success, const QString& message) {
            m_ttsModelsLoaded++;
            if (success) {
                FINE_DEBUG_OUTPUT("[TTS Operation]Model set: true, Message: " + message
                    + "(" + QString::number(m_ttsModelsLoaded) + "/2)");
            }
            else {
                ERROR_DEBUG_OUTPUT("[TTS Operation]Model set: false, Message: " + message
                    + "(" + QString::number(m_ttsModelsLoaded) + "/2)");
            }
            if (m_ttsModelsLoaded >= 2) {
                FINE_DEBUG_OUTPUT(QString("[Startup] TTS models ready: %1 ms")
                    .arg(m_ttsWeightTimer.isValid() ? m_ttsWeightTimer.elapsed() : -1));
            }
        });

    const bool reloadWeights = GET_BOOL_FROM_JSON(_global_config, "tts", "reload_weights_on_start");
    if (reloadWeights) {
        m_ttsManager->setGPTWeights(GET_STRING_FROM_JSON(_global_config, "tts", "gpt_path"));
        m_ttsManager->setSovitsWeights(GET_STRING_FROM_JSON(_global_config, "tts", "sovits_path"));
        FINE_DEBUG_OUTPUT("[Startup] TTS weight switch queued (reload_weights_on_start=true)");
    }
    else {
        FINE_DEBUG_OUTPUT("[Startup] Skip TTS weight reload (reload_weights_on_start=false); yaml weights stay loaded");
    }
    m_ttsManager->warmup(ttsRequestParams);
    FINE_DEBUG_OUTPUT("[Startup] TTS warmup queued, connecting WebSocket without waiting");

    connect(m_audioRecorder, &AudioRecorder::errorOccurred,
        this, &MainController::onAudioError);
    connect(m_audioRecorder, &AudioRecorder::pcmFrameReady,
        this, &MainController::onPcmFrame, Qt::QueuedConnection);
    connect(m_audioRecorder, &AudioRecorder::speechDetected,
        this, &MainController::onSpeechDetected, Qt::QueuedConnection);

    if (m_tencentRecognizer) {
        m_tencentRecognizer->setParent(this);
    }
    connect(m_tencentRecognizer, &TencentSpeechRecognizer::errorOccurred,
        this, &MainController::onRecognizeError);
    connect(m_tencentRecognizer, &TencentSpeechRecognizer::transcriptReceived,
        this, &MainController::onTranscriptReceived);

    QString secretId = GET_STRING_FROM_JSON(_global_config, "tencent_speech_recognizer", "secret_id");
    QString secretKey = GET_STRING_FROM_JSON(_global_config, "tencent_speech_recognizer", "secret_key");
    QString appId = GET_STRING_FROM_JSON(_global_config, "tencent_speech_recognizer", "app_id");
    if (appId.isEmpty()) {
        const int appIdNum = GET_INT_FROM_JSON(_global_config, "tencent_speech_recognizer", "app_id");
        if (appIdNum > 0) {
            appId = QString::number(appIdNum);
        }
    }
    m_tencentRecognizer->setCredentials(secretId, secretKey, appId);
    m_tencentRecognizer->setVadSilenceTime(
        GET_INT_FROM_JSON(_global_config, "tencent_speech_recognizer", "vad_silence_time"));

    connect(m_webSocketController, &WebSocketController::connected,
        this, &MainController::onWebSocketConnected);
    connect(m_webSocketController, &WebSocketController::chatResponseReceived,
        this, &MainController::onWebSocketChatResponse);
    connect(m_webSocketController, &WebSocketController::errorOccurred,
        this, &MainController::onWebSocketError);
    connect(m_webSocketController, &WebSocketController::connectionStateChanged,
        this, &MainController::onWebSocketStateChanged);

    FINE_DEBUG_OUTPUT("[Startup] TTS warmup queued; WebSocket connect deferred until splash hooks are ready");

    if (m_userInputWidget) {
        connect(m_userInputWidget, &UserInputWidget::textSubmitted,
            this, &MainController::processInputText);
    }

}

MainController::~MainController()
{

}

void MainController::startSession()
{
    m_webSocketController->connectToServer();
    FINE_DEBUG_OUTPUT("[WebSocket] Connecting to: " + GET_STRING_FROM_JSON(_global_config, "aronalm", "websocket_url"));
}

void MainController::executeOutput(const QString& text)
{
    ttsRequestParams.text = text;
    ttsRequestParams.emotion = m_currentEmotion;
    m_ttsManager->requestTTSPost(ttsRequestParams);
}

void MainController::onTTSFinished(const QByteArray& audioData, const QString& mediaType, const QString& text, const QString& emotion)
{
    holdOrPresentOutput(audioData, mediaType, false, text, emotion);
}

void MainController::presentOutput(const QByteArray& audioData, const QString& mediaType, const QString& text, const QString& emotion)
{
    Q_UNUSED(mediaType);
    const QString line = text;
    const QString face = emotion.isEmpty() ? QStringLiteral("normal") : emotion;
    m_currentText = line;
    m_currentEmotion = face;
    ++m_outputGeneration;
    const int gen = m_outputGeneration;

    const double wavSec = m_ttsManager->playAudio(audioData);
    m_audioRecorder->setPlaybackGuard(true);
    m_bargeInGuardTimer.start();
    m_mainWidget->showOutputText(line);
    if (m_measuringUserTurn) {
        FINE_DEBUG_OUTPUT(QString("[Latency] User send to text on screen: %1 ms")
            .arg(m_userTurnTimer.elapsed()));
        m_measuringUserTurn = false;
    }
    int duration = qMax(500, line.size() * 100);
    if (wavSec > 0) {
        duration = static_cast<int>(1000 * wavSec);
    }
    const QString expressionAnim = AronaEmotion::toAnimationName(face);
    m_mainWidget->setAnimation(expressionAnim, 1, true);
    m_mainWidget->setAnimation("Arona_Work_In_1_CN", 2, true);
    QTimer::singleShot(duration, this, [this, gen]() {
        if (gen != m_outputGeneration) {
            return;
        }
        m_mainWidget->hideOutputText();
        m_mainWidget->clearAnimation(2, 0.2f);
        m_mainWidget->clearAnimation(1, 0.2f);
        m_audioRecorder->setPlaybackGuard(false);
        });
}

void MainController::onTTSError(const QString& errorString, const QString& text, const QString& emotion)
{
    ERROR_DEBUG_OUTPUT("[TTS Operation]TTS error: " + errorString);

    if (text.isEmpty()) {
        m_measuringUserTurn = false;
        if (m_awaitingStartupWelcome) {
            m_awaitingStartupWelcome = false;
            if (m_splashActive) {
                emit welcomePlaybackReady();
            }
        }
        m_ttsManager->notifyPlaybackFinished();
        return;
    }

    holdOrPresentOutput(QByteArray(), QString(), true, text, emotion);
}

void MainController::presentOutputError(const QString& text, const QString& emotion)
{
    const QString line = text;
    const QString face = emotion.isEmpty() ? QStringLiteral("normal") : emotion;
    m_currentText = line;
    m_currentEmotion = face;
    ++m_outputGeneration;
    const int gen = m_outputGeneration;

    m_mainWidget->showOutputText(line);
    if (m_measuringUserTurn) {
        FINE_DEBUG_OUTPUT(QString("[Latency] User send to text on screen: %1 ms")
            .arg(m_userTurnTimer.elapsed()));
        m_measuringUserTurn = false;
    }
    const QString expressionAnim = AronaEmotion::toAnimationName(face);
    m_mainWidget->setAnimation(expressionAnim, 1, true);
    int duration = qMax(1500, line.size() * 100);
    QTimer::singleShot(duration, this, [this, gen]() {
        if (gen != m_outputGeneration) {
            return;
        }
        m_mainWidget->hideOutputText();
        m_mainWidget->clearAnimation(1, 0.2f);
        });
    m_ttsManager->notifyPlaybackFinished();
}

void MainController::holdOrPresentOutput(const QByteArray& audioData, const QString& mediaType, bool isError, const QString& text, const QString& emotion)
{
    if (m_awaitingStartupWelcome) {
        m_awaitingStartupWelcome = false;
        if (m_splashActive) {
            m_hasPendingOutput = true;
            m_pendingIsError = isError;
            m_pendingAudio = audioData;
            m_pendingMediaType = mediaType;
            m_pendingText = text;
            m_pendingEmotion = emotion;
            FINE_DEBUG_OUTPUT(QString("[Main Controller] Welcome TTS %1, waiting for splash close")
                .arg(isError ? "error" : "ready"));
            emit welcomePlaybackReady();
            return;
        }
    }

    if (isError) {
        presentOutputError(text, emotion);
    } else {
        presentOutput(audioData, mediaType, text, emotion);
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
        presentOutputError(m_pendingText, m_pendingEmotion);
    } else {
        presentOutput(m_pendingAudio, m_pendingMediaType, m_pendingText, m_pendingEmotion);
    }
    m_pendingAudio.clear();
    m_pendingMediaType.clear();
    m_pendingText.clear();
    m_pendingEmotion.clear();
}

void MainController::dismissSplashOnUnrecoverableError()
{
    if (!m_splashActive) {
        return;
    }
    m_awaitingStartupWelcome = false;
    FINE_DEBUG_OUTPUT("[Main Controller] Unrecoverable WS error, dismissing splash");
    emit welcomePlaybackReady();
}

void MainController::startAudioProcessing()
{
    if (m_listening) {
        return;
    }
    if (!m_tencentRecognizer->isInitialized()) {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Realtime ASR is not initialized");
        return;
    }
    if (!m_audioRecorder->startRecording()) {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Failed to start recording");
        return;
    }
    if (!m_tencentRecognizer->startRealtime()) {
        m_audioRecorder->stopRecording();
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Failed to start realtime ASR");
        return;
    }
    m_listening = true;
    m_transcriptSeq = 0;
    m_webSocketController->sendListenState(true);
    FINE_DEBUG_OUTPUT("[Audio Input Processing]Continuous listen on");
}

bool MainController::isListening() const
{
    return m_listening;
}

void MainController::stopAudioProcessing()
{
    if (!m_listening) {
        m_audioRecorder->stopRecording();
        m_tencentRecognizer->stopRealtime();
        return;
    }
    m_listening = false;
    m_audioRecorder->stopRecording();
    m_audioRecorder->setPlaybackGuard(false);
    m_tencentRecognizer->stopRealtime();
    m_webSocketController->sendListenState(false);
    FINE_DEBUG_OUTPUT("[Audio Input Processing]Continuous listen off");
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

void MainController::onPcmFrame(const QByteArray& frame)
{
    if (!m_listening) {
        return;
    }
    m_tencentRecognizer->sendAudio(frame);
}

void MainController::onSpeechDetected()
{
    if (!m_listening) {
        return;
    }
    if (m_bargeInGuardTimer.isValid() && m_bargeInGuardTimer.elapsed() < 400) {
        return;
    }
    if (m_ttsManager->isPlayingAudio() || m_waitingForAIResponse || m_hasPendingOutput) {
        FINE_DEBUG_OUTPUT("[Audio Input Processing]Barge-in speech detected");
        interruptOutput();
        return;
    }
    if (m_webSocketController->isConnected()) {
        m_webSocketController->sendInterrupt();
    }
}

void MainController::interruptOutput()
{
    FINE_DEBUG_OUTPUT("[Main Controller] Interrupting output");
    ++m_outputGeneration;
    m_ttsManager->interruptPlayback();
    m_audioRecorder->setPlaybackGuard(false);
    m_waitingForAIResponse = false;
    m_measuringUserTurn = false;
    m_mainWidget->hideOutputText();
    m_mainWidget->clearAnimation(2, 0.2f);
    m_mainWidget->clearAnimation(1, 0.2f);
    if (m_webSocketController->isConnected()) {
        m_webSocketController->sendInterrupt();
    }
}

void MainController::onRecognizeError(const QString& error)
{
    ERROR_DEBUG_OUTPUT("[Audio Input Processing]Recognize error: " + error);
}

void MainController::onTranscriptReceived(const QString& text, bool isFinal, int sliceType)
{
    const QString trimmed = text.trimmed();
    FINE_DEBUG_OUTPUT(QString("[Audio Input Processing]ASR slice=%1 final=%2 text=%3")
        .arg(sliceType)
        .arg(isFinal ? "true" : "false")
        .arg(trimmed));
    if (!m_listening || !isFinal || trimmed.isEmpty()) {
        return;
    }
    if (trimmed.contains(QStringLiteral("[Tencent Speech Recognizer]"))
        || trimmed.contains(QStringLiteral("Didnt recognize"), Qt::CaseInsensitive)
        || trimmed.contains(QStringLiteral("Didn't recognize"), Qt::CaseInsensitive)) {
        ERROR_DEBUG_OUTPUT("[Audio Input Processing]Ignoring unusable ASR text");
        return;
    }
    if (!m_webSocketController->isConnected()) {
        ERROR_DEBUG_OUTPUT("[Main Controller] WebSocket not connected, drop transcript");
        return;
    }
    ++m_transcriptSeq;
    m_webSocketController->sendTranscript(
        trimmed,
        QString::number(m_transcriptSeq),
        0);
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
    FINE_DEBUG_OUTPUT("[Main Controller] Generating responce...");

    // 发送消息给AI服务端
    // 可以从配置中读取是否使用 RAG、记忆等功能
    bool useRag = GET_BOOL_FROM_JSON(_global_config, "aronalm", "use_rag");
    bool useMemory = GET_BOOL_FROM_JSON(_global_config, "aronalm", "use_memory");

    m_backendTimer.restart();
    m_userTurnTimer.restart();
    m_measuringUserTurn = true;

    m_webSocketController->sendChatMessage(trimmed, useRag, useMemory);

    FINE_DEBUG_OUTPUT("[Main Controller] Sent to AI service: " + trimmed.left(50) + "...");
}

void MainController::onWebSocketConnected(const QString& sessionId)
{
    FINE_DEBUG_OUTPUT("[WebSocket] Connected! Session ID: " + sessionId);
    FINE_DEBUG_OUTPUT(QString("[Startup] WebSocket connected, TTS models reloaded: %1/2")
        .arg(m_ttsModelsLoaded));
}

void MainController::onWebSocketChatResponse(const QString& content, const QString& contextUsed, double latency, const QString& emotion)
{
    FINE_DEBUG_OUTPUT(QString("[Latency] Backend RTT: %1 ms (server_reported: %2s)")
        .arg(m_backendTimer.elapsed())
        .arg(latency, 0, 'f', 2));
    FINE_DEBUG_OUTPUT("[WebSocket] Received AI response: " + content.left(50) + "...");
    FINE_DEBUG_OUTPUT(QString("[WebSocket] Context: %1, Latency: %2s, Emotion: %3")
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
        m_currentText = userMessage;
        m_currentEmotion = QStringLiteral("normal");
        m_hasPendingOutput = true;
        m_pendingIsError = true;
        dismissSplashOnUnrecoverableError();
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
