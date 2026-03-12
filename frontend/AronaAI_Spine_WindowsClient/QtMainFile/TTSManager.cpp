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
{
    // 设置服务器地址
    setServerAddress(GET_STRING_FROM_JSON(_global_config, "tts", "host"), GET_INT_FROM_JSON(_global_config, "tts", "port"));
    qDebug().noquote() << FINE_PR << "[TTS Operation]Set server : Host: " << serverHost << " | Port: " << serverPort;

	// 初始化TTSRequestParams
    ttsRequestParams.text = "";  // 要合成的文本
    ttsRequestParams.textLang = "zh";    // 文本语言
    ttsRequestParams.refAudioPath = "";  // 参考音频路径
    ttsRequestParams.auxRefAudioPaths;   // 辅助参考音频路径
    ttsRequestParams.promptText = "";    // 提示文本
    ttsRequestParams.promptLang = "zh";  // 提示文本语言
    ttsRequestParams.topK = 5;   // top k采样
    ttsRequestParams.topP = 1.0;  // top p采样
    ttsRequestParams.temperature = 1.0;   // 温度参数
    ttsRequestParams.textSplitMethod = "cut0";   // 文本分割方法
    ttsRequestParams.batchSize = 1;  // 批处理大小
    ttsRequestParams.batchThreshold = 0.75;   // 批处理阈值
    ttsRequestParams.splitBucket = true;    // 是否分割桶
    ttsRequestParams.speedFactor = 1.0;   // 语速因子
    ttsRequestParams.fragmentInterval = 0.3;  // 片段间隔
    ttsRequestParams.seed = -1;  // 随机种子
    ttsRequestParams.streamingMode = false; // 流式模式
    ttsRequestParams.parallelInfer = true;  // 并行推理
    ttsRequestParams.repetitionPenalty = 1.35;    // 重复惩罚
    ttsRequestParams.sampleSteps = 32;   // 采样步数
    ttsRequestParams.superSampling = false; // 超采样
    ttsRequestParams.mediaType = "wav";  // 媒体类型

	// 连接网络请求完成的信号到槽函数
    connect(networkManager, &QNetworkAccessManager::finished,
        this, &TTSManager::onNetworkReplyFinished);

}

TTSManager::~TTSManager()
{
    if (currentReply) {
        currentReply->abort();
        currentReply->deleteLater();
    }
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

    if (!params.auxRefAudioPaths.isEmpty()) {
        QJsonArray auxPaths;
        for (const QString& path : params.auxRefAudioPaths) {
            auxPaths.append(path);
        }
        json["aux_ref_audio_paths"] = auxPaths;
    }

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

    return json;
}

void TTSManager::requestTTSGet(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");
    url.setQuery(buildQueryFromParams(params));

    QNetworkRequest request(url);
    currentMediaType = params.mediaType;

    if (currentReply) {
        currentReply->abort();
        currentReply->deleteLater();
    }

    currentReply = networkManager->get(request);

    if (params.streamingMode) {
        connect(currentReply, &QNetworkReply::readyRead,
            this, &TTSManager::onStreamReadyRead);
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onStreamFinished);
    }

    accumulatedAudioData.clear();
}

void TTSManager::requestTTSPost(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");

    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");

    QJsonObject json = buildJsonFromParams(params);
    QJsonDocument doc(json);
    QByteArray data = doc.toJson();

    currentMediaType = params.mediaType;

    if (currentReply) {
        currentReply->abort();
        currentReply->deleteLater();
    }

    currentReply = networkManager->post(request, data);

    if (params.streamingMode) {
        connect(currentReply, &QNetworkReply::readyRead,
            this, &TTSManager::onStreamReadyRead);
        connect(currentReply, &QNetworkReply::finished,
            this, &TTSManager::onStreamFinished);
    }

    accumulatedAudioData.clear();
}

void TTSManager::sendControlCommand(const QString& command)
{
    QUrl url = buildBaseUrl();
    url.setPath("/control");

    QUrlQuery query;
    query.addQueryItem("command", command);
    url.setQuery(query);

    QNetworkRequest request(url);
    QNetworkReply* reply = networkManager->get(request);

    connect(reply, &QNetworkReply::finished, [this, reply]() {
        if (reply->error() == QNetworkReply::NoError) {
            emit commandFinished(true, "Command executed successfully");
        }
        else {
            emit commandFinished(false, reply->errorString());
        }
        reply->deleteLater();
        });
}

void TTSManager::setGPTWeights(const QString& weightsPath)
{
    QUrl url = buildBaseUrl();
    url.setPath("/set_gpt_weights");

    QUrlQuery query;
    query.addQueryItem("weights_path", weightsPath);
    url.setQuery(query);

    QNetworkRequest request(url);
    QNetworkReply* reply = networkManager->get(request);

    connect(reply, &QNetworkReply::finished, [this, reply]() {
        if (reply->error() == QNetworkReply::NoError) {
            QByteArray data = reply->readAll();
            if (data.contains("success")) {
                emit modelSwitched(true, "GPT model switched successfully");
            }
            else {
                emit modelSwitched(false, QString::fromUtf8(data));
            }
        }
        else {
            emit modelSwitched(false, reply->errorString());
        }
        reply->deleteLater();
        });
}

void TTSManager::setSovitsWeights(const QString& weightsPath)
{
    QUrl url = buildBaseUrl();
    url.setPath("/set_sovits_weights");

    QUrlQuery query;
    query.addQueryItem("weights_path", weightsPath);
    url.setQuery(query);

    QNetworkRequest request(url);
    QNetworkReply* reply = networkManager->get(request);

    connect(reply, &QNetworkReply::finished, [this, reply]() {
        if (reply->error() == QNetworkReply::NoError) {
            QByteArray data = reply->readAll();
            if (data.contains("success")) {
                emit modelSwitched(true, "Sovits model switched successfully");
            }
            else {
                emit modelSwitched(false, QString::fromUtf8(data));
            }
        }
        else {
            emit modelSwitched(false, reply->errorString());
        }
        reply->deleteLater();
        });
}

void TTSManager::onNetworkReplyFinished()
{
    QNetworkReply* reply = qobject_cast<QNetworkReply*>(sender());
    if (!reply) return;

    reply->deleteLater();

    if (reply->error() != QNetworkReply::NoError) {
        emit ttsError(reply->errorString());
        return;
    }

    // 检查是否是TTS请求
    if (reply->url().path() == "/tts") {
        handleTTSResponse(reply);
    }
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
    if (!accumulatedAudioData.isEmpty()) {
        emit ttsFinished(accumulatedAudioData, currentMediaType);
    }
    accumulatedAudioData.clear();
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
    format.setSampleRate(24000); // 根据实际音频采样率调整
    format.setChannelCount(1);
    format.setSampleFormat(QAudioFormat::Int16);

    // 检查设备是否支持该格式
    QAudioDevice audioDevice = QMediaDevices::defaultAudioOutput();
    if (!audioDevice.isFormatSupported(format)) {
        qWarning() << "Default format not supported, trying to use preferred format";
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