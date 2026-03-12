#include "TTSManager.h"
#include <QDebug>
#include <QHttpMultiPart>
#include <QAudioFormat>
#include <QAudioSink>

TTSManager::TTSManager(QObject* parent)
    : QObject(parent)
    , networkManager(new QNetworkAccessManager(this))
    , currentReply(nullptr)
    , audioSink(nullptr)
    , audioBuffer(nullptr)
    , isProcessingRequest(false)
    , isStreamingMode(false)
{
    // 设置服务器地址
    setServerAddress(GET_STRING_FROM_JSON(_global_config, "tts", "host"), GET_INT_FROM_JSON(_global_config, "tts", "port"));
    qDebug().noquote() << FINE_PR << "[TTS Operation]Set server : Host: " << serverHost << " | Port: " << serverPort;

	// 连接网络请求完成的信号到槽函数
    connect(networkManager, &QNetworkAccessManager::finished,
        this, &TTSManager::onNetworkReplyFinished);

}

TTSManager::~TTSManager()
{
    cleanupCurrentReply();
    requestQueue.clear();  // 清空请求队列

    if (audioSink) {
        audioSink->stop();
        delete audioSink;
    }
    if (audioBuffer) {
        delete audioBuffer;
    }
}

void TTSManager::setServerAddress(const QString& host, int port)
{
    serverHost = host;
    serverPort = port;
}

void TTSManager::cleanupCurrentReply()
{
    if (currentReply) {
        // 断开所有连接
        currentReply->disconnect();
        currentReply->abort();
        currentReply->deleteLater();
        currentReply = nullptr;
    }
    accumulatedAudioData.clear();
    isStreamingMode = false;
}

QUrl TTSManager::buildBaseUrl() const
{
    QUrl url;
    url.setScheme("http");
    url.setHost(serverHost);
    url.setPort(serverPort);
    return url;
}

QUrlQuery TTSManager::buildQueryFromParams(const TTSRequestParams& params) const
{
    QUrlQuery query;
    query.addQueryItem("text", params.text);
    query.addQueryItem("text_lang", params.textLang);
    query.addQueryItem("ref_audio_path", params.refAudioPath);

    if (!params.auxRefAudioPaths.isEmpty()) {
        query.addQueryItem("aux_ref_audio_paths", params.auxRefAudioPaths.join(","));
    }

    query.addQueryItem("prompt_lang", params.promptLang);
    query.addQueryItem("prompt_text", params.promptText);
    query.addQueryItem("top_k", QString::number(params.topK));
    query.addQueryItem("top_p", QString::number(params.topP));
    query.addQueryItem("temperature", QString::number(params.temperature));
    query.addQueryItem("text_split_method", params.textSplitMethod);
    query.addQueryItem("batch_size", QString::number(params.batchSize));
    query.addQueryItem("batch_threshold", QString::number(params.batchThreshold));
    query.addQueryItem("split_bucket", params.splitBucket ? "true" : "false");
    query.addQueryItem("speed_factor", QString::number(params.speedFactor));
    query.addQueryItem("fragment_interval", QString::number(params.fragmentInterval));
    query.addQueryItem("seed", QString::number(params.seed));
    query.addQueryItem("media_type", params.mediaType);
    query.addQueryItem("streaming_mode", params.streamingMode ? "true" : "false");
    query.addQueryItem("parallel_infer", params.parallelInfer ? "true" : "false");
    query.addQueryItem("repetition_penalty", QString::number(params.repetitionPenalty));
    query.addQueryItem("sample_steps", QString::number(params.sampleSteps));
    query.addQueryItem("super_sampling", params.superSampling ? "true" : "false");

    return query;
}

QJsonObject TTSManager::buildJsonFromParams(const TTSRequestParams& params) const
{
    QJsonObject json;
    json["text"] = params.text;
    json["text_lang"] = params.textLang;
    json["ref_audio_path"] = params.refAudioPath;

    QJsonArray auxPaths;
    if (!params.auxRefAudioPaths.isEmpty()) {
        for (const QString& path : params.auxRefAudioPaths) {
            auxPaths.append(path);
        }
    }
    json["aux_ref_audio_paths"] = auxPaths;

    json["prompt_lang"] = params.promptLang;
    json["prompt_text"] = params.promptText;
    json["top_k"] = params.topK;
    json["top_p"] = params.topP;
    json["temperature"] = params.temperature;
    json["text_split_method"] = params.textSplitMethod;
    json["batch_size"] = params.batchSize;
    json["batch_threshold"] = params.batchThreshold;
    json["split_bucket"] = params.splitBucket;
    json["speed_factor"] = params.speedFactor;
    json["fragment_interval"] = params.fragmentInterval;
    json["seed"] = params.seed;
    json["media_type"] = params.mediaType;
    json["streaming_mode"] = params.streamingMode;
    json["parallel_infer"] = params.parallelInfer;
    json["repetition_penalty"] = params.repetitionPenalty;
    json["sample_steps"] = params.sampleSteps;
    json["super_sampling"] = params.superSampling;

	// 调试：输出构建的JSON对象
	QJsonDocument jsonDoc(json);
    qDebug().noquote() << jsonDoc.toJson(QJsonDocument::Indented);

    return json;
}

void TTSManager::requestTTSGet(const TTSRequestParams& params)
{
    requestQueue.enqueue(QueuedRequest(QueuedRequest::TTSGet, params));
    processNextRequest();
}

void TTSManager::requestTTSPost(const TTSRequestParams& params)
{
    requestQueue.enqueue(QueuedRequest(QueuedRequest::TTSPost, params));
    processNextRequest();
}

void TTSManager::sendControlCommand(const QString& command)
{
    requestQueue.enqueue(QueuedRequest(QueuedRequest::ControlCommand, command));
    processNextRequest();
}

void TTSManager::setGPTWeights(const QString& weightsPath)
{
    requestQueue.enqueue(QueuedRequest(QueuedRequest::SetGPTWeights, weightsPath, true));
    processNextRequest();
}

void TTSManager::setSovitsWeights(const QString& weightsPath)
{
    requestQueue.enqueue(QueuedRequest(QueuedRequest::SetSovitsWeights, weightsPath, true));
    processNextRequest();
}

void TTSManager::onNetworkReplyFinished()
{
    QNetworkReply* reply = qobject_cast<QNetworkReply*>(sender());
    if (!reply || reply != currentReply) {
        // 如果不是当前请求的回复，忽略并清理
        if (reply) {
            reply->deleteLater();
        }
        return;
    }

    if (reply->error() != QNetworkReply::NoError) {
        emit ttsError(reply->errorString());
    }
    else {
        // 检查是否是TTS请求
        if (reply->url().path() == "/tts") {
            handleTTSResponse(reply);
        }
    }

    // 清理当前回复并处理下一个请求
    cleanupCurrentReply();
    isProcessingRequest = false;
    processNextRequest();
}

void TTSManager::onStreamReadyRead()
{
    if (!currentReply) return;

    QByteArray chunk = currentReply->readAll();
    if (!chunk.isEmpty()) {
        accumulatedAudioData.append(chunk);
        emit ttsChunkReceived(chunk);
    }
}

void TTSManager::onStreamFinished()
{
    if (!currentReply) return;

    if (!accumulatedAudioData.isEmpty()) {
        emit ttsFinished(accumulatedAudioData, currentMediaType);
    }
    accumulatedAudioData.clear();

    // 清理当前回复并处理下一个请求
    cleanupCurrentReply();
    isProcessingRequest = false;
    processNextRequest();
}

void TTSManager::handleTTSResponse(QNetworkReply* reply)
{
    if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 200) {
        QByteArray audioData = reply->readAll();

        // 检查是否是JSON错误响应
        if (audioData.startsWith('{') && audioData.contains("message")) {
            QJsonDocument doc = QJsonDocument::fromJson(audioData);
            if (doc.isObject()) {
                QString errorMsg = doc.object()["message"].toString();
                emit ttsError(errorMsg);
                return;
            }
        }

        emit ttsFinished(audioData, currentMediaType);
    }
    else {
        QByteArray errorData = reply->readAll();
        QString errorMsg = QString::fromUtf8(errorData);
        if (errorData.startsWith('{')) {
            QJsonDocument doc = QJsonDocument::fromJson(errorData);
            if (doc.isObject()) {
                errorMsg = doc.object()["message"].toString();
            }
        }
        emit ttsError(errorMsg);
    }
}

void TTSManager::playAudio(const QByteArray& audioData)
{
    if (audioData.isEmpty()) return;

    // 停止当前播放
    if (audioSink && audioSink->state() == QAudio::ActiveState) {
        audioSink->stop();
    }

    // 创建音频格式
    QAudioFormat format;
    format.setSampleRate(32000); // 根据实际音频采样率调整
    format.setChannelCount(1);
    format.setSampleFormat(QAudioFormat::Int16);

    // 检查设备是否支持该格式
    QAudioDevice audioDevice = QMediaDevices::defaultAudioOutput();
    if (!audioDevice.isFormatSupported(format)) {
        qWarning() << ERROR_PR << "Default format not supported, trying to use preferred format";
        format = audioDevice.preferredFormat();
    }

    // 创建音频缓冲区
    if (audioBuffer) {
        delete audioBuffer;
    }
    audioBuffer = new QBuffer(this);
    audioBuffer->setData(audioData);
    audioBuffer->open(QIODevice::ReadOnly);

    // 创建音频输出
    if (!audioSink) {
        audioSink = new QAudioSink(audioDevice, format, this);
    }

    audioSink->start(audioBuffer);
}

bool TTSManager::saveAudioToFile(const QByteArray& audioData, const QString& filePath)
{
    QFile file(filePath);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(audioData);
        file.close();
        return true;
    }
    return false;
}

double TTSManager::getWavDuration(const QByteArray& audioData)
{
    // WAV文件头结构
    struct WavHeader {
        // RIFF头
        char riffId[4];        // "RIFF"
        quint32 riffSize;       // 文件大小-8
        char waveId[4];         // "WAVE"

        // fmt块
        char fmtId[4];          // "fmt "
        quint32 fmtSize;        // fmt块大小
        quint16 audioFormat;     // 音频格式 (1 = PCM)
        quint16 numChannels;     // 声道数
        quint32 sampleRate;      // 采样率
        quint32 byteRate;        // 字节率 = sampleRate * numChannels * bitsPerSample/8
        quint16 blockAlign;      // 块对齐 = numChannels * bitsPerSample/8
        quint16 bitsPerSample;   // 位深度
    };

    if (audioData.size() < sizeof(WavHeader)) {
        qWarning() << "WAV数据太小，无法读取头部";
        return -1;
    }

    // 将数据复制到头结构
    WavHeader header;
    memcpy(&header, audioData.constData(), sizeof(WavHeader));

    // 验证是否为有效的WAV文件
    if (memcmp(header.riffId, "RIFF", 4) != 0 ||
        memcmp(header.waveId, "WAVE", 4) != 0 ||
        memcmp(header.fmtId, "fmt ", 4) != 0) {
        qWarning() << "无效的WAV文件格式";
        return -1;
    }

    // 查找data块
    int offset = sizeof(WavHeader);
    while (offset < audioData.size() - 8) {
        char chunkId[4];
        quint32 chunkSize;

        memcpy(chunkId, audioData.constData() + offset, 4);
        memcpy(&chunkSize, audioData.constData() + offset + 4, 4);

        if (memcmp(chunkId, "data", 4) == 0) {
            // 找到data块
            quint32 dataSize = chunkSize;

            // 计算时长：数据大小 / (采样率 * 声道数 * 位深度/8)
            double duration = static_cast<double>(dataSize) /
                (header.sampleRate * header.numChannels * (header.bitsPerSample / 8.0));

            qDebug() << "WAV信息:"
                << "采样率:" << header.sampleRate
                << "声道数:" << header.numChannels
                << "位深度:" << header.bitsPerSample
                << "数据大小:" << dataSize
                << "时长:" << duration << "秒";

            return duration;
        }

        offset += 8 + chunkSize;
    }

    qWarning() << "未找到data块";
    return -1;
}

void TTSManager::processNextRequest()
{
    // 如果正在处理请求或队列为空，则返回
    if (isProcessingRequest || requestQueue.isEmpty()) {
        return;
    }

    isProcessingRequest = true;
    QueuedRequest request = requestQueue.dequeue();

    switch (request.type) {
    case QueuedRequest::TTSGet:
        executeTTSGet(request.params);
        break;
    case QueuedRequest::TTSPost:
        executeTTSPost(request.params);
        break;
    case QueuedRequest::ControlCommand:
        executeControlCommand(request.command);
        break;
    case QueuedRequest::SetGPTWeights:
        executeSetGPTWeights(request.weightsPath);
        break;
    case QueuedRequest::SetSovitsWeights:
        executeSetSovitsWeights(request.weightsPath);
        break;
    }
}

void TTSManager::executeTTSGet(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");
    url.setQuery(buildQueryFromParams(params));

    QNetworkRequest request(url);
    currentMediaType = params.mediaType;
    isStreamingMode = params.streamingMode;

    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    if (params.streamingMode) {
        connect(currentReply, &QNetworkReply::readyRead,
            this, &TTSManager::onStreamReadyRead);
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onStreamFinished);
    }
    else {
        // 非流式模式，使用原有的finished信号
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onNetworkReplyFinished);
    }

    accumulatedAudioData.clear();
}

void TTSManager::executeTTSPost(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");

    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");

    QJsonObject json = buildJsonFromParams(params);
    QJsonDocument doc(json);
    QByteArray data = doc.toJson();

    currentMediaType = params.mediaType;
    isStreamingMode = params.streamingMode;

    cleanupCurrentReply();
    currentReply = networkManager->post(request, data);

    if (params.streamingMode) {
        connect(currentReply, &QNetworkReply::readyRead,
            this, &TTSManager::onStreamReadyRead);
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onStreamFinished);
    }
    else {
        // 非流式模式，使用原有的finished信号
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onNetworkReplyFinished);
    }

    accumulatedAudioData.clear();
}

void TTSManager::executeControlCommand(const QString& command)
{
    QUrl url = buildBaseUrl();
    url.setPath("/control");

    QUrlQuery query;
    query.addQueryItem("command", command);
    url.setQuery(query);

    QNetworkRequest request(url);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (currentReply->error() == QNetworkReply::NoError) {
            emit commandFinished(true, "Command executed successfully");
        }
        else {
            emit commandFinished(false, currentReply->errorString());
        }

        // 清理并处理下一个请求
        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        });
}

void TTSManager::executeSetGPTWeights(const QString& weightsPath)
{
    QUrl url = buildBaseUrl();
    url.setPath("/set_gpt_weights");

    QUrlQuery query;
    query.addQueryItem("weights_path", weightsPath);
    url.setQuery(query);

    QNetworkRequest request(url);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (currentReply->error() == QNetworkReply::NoError) {
            QByteArray data = currentReply->readAll();
            if (data.contains("success")) {
                emit modelSwitched(true, "GPT model switched successfully");
            }
            else {
                emit modelSwitched(false, QString::fromUtf8(data));
            }
        }
        else {
            emit modelSwitched(false, currentReply->errorString());
        }

        // 清理并处理下一个请求
        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        });
}

void TTSManager::executeSetSovitsWeights(const QString& weightsPath)
{
    QUrl url = buildBaseUrl();
    url.setPath("/set_sovits_weights");

    QUrlQuery query;
    query.addQueryItem("weights_path", weightsPath);
    url.setQuery(query);

    QNetworkRequest request(url);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (currentReply->error() == QNetworkReply::NoError) {
            QByteArray data = currentReply->readAll();
            if (data.contains("success")) {
                emit modelSwitched(true, "Sovits model switched successfully");
            }
            else {
                emit modelSwitched(false, QString::fromUtf8(data));
            }
        }
        else {
            emit modelSwitched(false, currentReply->errorString());
        }

        // 清理并处理下一个请求
        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        });
}
