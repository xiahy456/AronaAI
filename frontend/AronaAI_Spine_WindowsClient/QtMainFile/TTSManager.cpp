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

#include "TTSManager.h"
#include <QDebug>
#include <QHttpMultiPart>
#include <QAudio>
#include <QAudioFormat>
#include <QAudioSink>
#include <QTimer>
#include <cstring>

TTSManager::TTSManager(QObject* parent)
    : QObject(parent)
    , networkManager(new QNetworkAccessManager(this))
    , currentReply(nullptr)
    , audioSink(nullptr)
    , audioBuffer(nullptr)
    , isProcessingRequest(false)
    , m_awaitingPlayback(false)
    , m_playingAudio(false)
    , m_ignoreAudioIdle(false)
    , m_currentIsWarmup(false)
    , m_playbackGeneration(0)
    , requestTimeoutMs(45000)
{
    // 设置服务器地址
    setServerAddress(GET_STRING_FROM_JSON(_global_config, "tts", "host"), GET_INT_FROM_JSON(_global_config, "tts", "port"));
    FINE_DEBUG_OUTPUT("[TTS Operation]Set server : Host: " + serverHost + " | Port: " + QString::number(serverPort));

    int configuredTimeout = GET_INT_FROM_JSON(_global_config, "tts", "request_timeout_ms");
    if (configuredTimeout > 0) {
        requestTimeoutMs = configuredTimeout;
    }
    FINE_DEBUG_OUTPUT("[TTS Operation]Request timeout: " + QString::number(requestTimeoutMs) + " ms");

	// 连接网络请求完成的信号到槽函数
    connect(networkManager, &QNetworkAccessManager::finished,
        this, &TTSManager::onNetworkReplyFinished);

}

TTSManager::~TTSManager()
{
    cleanupCurrentReply();
    requestQueue.clear();
    m_readyPlayback.clear();

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
}

QUrl TTSManager::buildBaseUrl() const
{
    QUrl url;
    url.setScheme("http");
    url.setHost(serverHost);
    url.setPort(serverPort);
    return url;
}

void TTSManager::applyRequestTimeout(QNetworkRequest& request) const
{
    if (requestTimeoutMs > 0) {
        request.setTransferTimeout(requestTimeoutMs);
    }
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
    query.addQueryItem("streaming_mode", "false");
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
    json["streaming_mode"] = false;
    json["parallel_infer"] = params.parallelInfer;
    json["repetition_penalty"] = params.repetitionPenalty;
    json["sample_steps"] = params.sampleSteps;
    json["super_sampling"] = params.superSampling;

	// 输出构建的文本
    FINE_DEBUG_OUTPUT("[TTS Operation]Generate text: " + params.text);

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

void TTSManager::warmup(const TTSRequestParams& params)
{
    if (!params.refAudioPath.isEmpty()) {
        requestQueue.enqueue(QueuedRequest(QueuedRequest::SetReferAudio, params.refAudioPath, true));
    }
    TTSRequestParams warm = params;
    warm.text = QStringLiteral("老师好。");
    warm.emotion.clear();
    requestQueue.enqueue(QueuedRequest(QueuedRequest::WarmupTTS, warm));
    FINE_DEBUG_OUTPUT("[TTS Operation]Warmup queued (set_refer_audio + short /tts)");
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

    const bool isTts = reply->url().path() == QLatin1String("/tts");
    const bool warmup = m_currentIsWarmup;
    if (isTts) {
        if (reply->error() != QNetworkReply::NoError) {
            FINE_DEBUG_OUTPUT(QString("[Latency] TTS RTT: %1 ms (%2error)")
                .arg(m_ttsRequestTimer.elapsed())
                .arg(warmup ? QStringLiteral("warmup ") : QString()));
        }
        else {
            FINE_DEBUG_OUTPUT(QString("[Latency] TTS RTT: %1 ms%2")
                .arg(m_ttsRequestTimer.elapsed())
                .arg(warmup ? QStringLiteral(" (warmup)") : QString()));
        }
    }

    if (warmup) {
        if (reply->error() != QNetworkReply::NoError) {
            ERROR_DEBUG_OUTPUT("[TTS Operation]Warmup failed: " + reply->errorString());
        }
        else {
            FINE_DEBUG_OUTPUT("[TTS Operation]Warmup /tts complete");
        }
        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        return;
    }

    if (isTts) {
        QString errorMsg;
        const bool httpError = reply->error() != QNetworkReply::NoError;
        if (httpError) {
            errorMsg = reply->errorString();
            if (reply->error() == QNetworkReply::TimeoutError
                || reply->error() == QNetworkReply::OperationCanceledError) {
                errorMsg = QString("TTS request timed out after %1 ms").arg(requestTimeoutMs);
            }
        }
        enqueueTtsPlaybackFromReply(reply, httpError, errorMsg);
        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        tryDeliverPlayback();
        return;
    }

    cleanupCurrentReply();
    isProcessingRequest = false;
    processNextRequest();
}

void TTSManager::enqueueTtsPlaybackFromReply(QNetworkReply* reply, bool httpError, const QString& errorString)
{
    ReadyPlayback item;
    item.text = currentTtsText;
    item.emotion = currentTtsEmotion;
    item.mediaType = currentMediaType;

    if (httpError) {
        item.isError = true;
        item.errorString = errorString;
        m_readyPlayback.enqueue(item);
        return;
    }

    if (reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 200) {
        QByteArray audioData = reply->readAll();

        if (audioData.startsWith('{') && audioData.contains("message")) {
            QJsonDocument doc = QJsonDocument::fromJson(audioData);
            if (doc.isObject()) {
                item.isError = true;
                item.errorString = doc.object()["message"].toString();
                m_readyPlayback.enqueue(item);
                return;
            }
        }

        item.audioData = audioData;
        m_readyPlayback.enqueue(item);
        return;
    }

    QByteArray errorData = reply->readAll();
    QString errorMsg = QString::fromUtf8(errorData);
    if (errorData.startsWith('{')) {
        QJsonDocument doc = QJsonDocument::fromJson(errorData);
        if (doc.isObject()) {
            errorMsg = doc.object()["message"].toString();
        }
    }
    item.isError = true;
    item.errorString = errorMsg;
    m_readyPlayback.enqueue(item);
}

void TTSManager::tryDeliverPlayback()
{
    if (m_awaitingPlayback || m_readyPlayback.isEmpty()) {
        return;
    }
    ReadyPlayback item = m_readyPlayback.dequeue();
    m_awaitingPlayback = true;
    if (item.isError) {
        emit ttsError(item.errorString, item.text, item.emotion);
    }
    else {
        emit ttsFinished(item.audioData, item.mediaType, item.text, item.emotion);
    }
}

void TTSManager::notifyPlaybackFinished()
{
    if (!m_awaitingPlayback) {
        return;
    }
    m_awaitingPlayback = false;
    m_playingAudio = false;
    m_playbackGeneration++;
    tryDeliverPlayback();
}

double TTSManager::playAudio(const QByteArray& audioData)
{
    if (audioData.isEmpty()) {
        notifyPlaybackFinished();
        return -1;
    }

    WavPcmInfo wav;
    QByteArray pcm = audioData;
    int sampleRate = 32000;
    int channelCount = 1;
    double duration = -1;
    if (extractWavPcm(audioData, &wav)) {
        pcm = wav.pcm;
        sampleRate = wav.sampleRate;
        channelCount = wav.channelCount;
        duration = wav.durationSec;
    }
    else {
        ERROR_DEBUG_OUTPUT("[TTS Operation]WAV parse failed, playing bytes as raw PCM");
    }

    // 队列播下一条时才 stop；此时上一条应已结束
    m_ignoreAudioIdle = true;
    if (audioSink) {
        audioSink->stop();
        delete audioSink;
        audioSink = nullptr;
    }

    QAudioFormat format;
    format.setSampleRate(sampleRate);
    format.setChannelCount(channelCount);
    format.setSampleFormat(QAudioFormat::Int16);

    QAudioDevice audioDevice = QMediaDevices::defaultAudioOutput();
    if (!audioDevice.isFormatSupported(format)) {
        ERROR_DEBUG_OUTPUT("[TTS Operation]Default format not supported, trying to use preferred format");
        format = audioDevice.preferredFormat();
    }

    if (audioBuffer) {
        delete audioBuffer;
    }
    audioBuffer = new QBuffer(this);
    audioBuffer->setData(pcm);
    audioBuffer->open(QIODevice::ReadOnly);

    audioSink = new QAudioSink(audioDevice, format, this);
    connect(audioSink, &QAudioSink::stateChanged, this, [this](QAudio::State state) {
        if (m_ignoreAudioIdle || !m_playingAudio) {
            return;
        }
        if (state == QAudio::IdleState || state == QAudio::StoppedState) {
            notifyPlaybackFinished();
        }
    });

    m_playingAudio = true;
    audioSink->start(audioBuffer);
    m_ignoreAudioIdle = false;

    const int fallbackMs = duration > 0 ? static_cast<int>(duration * 1000.0) + 500 : 10000;
    const int gen = ++m_playbackGeneration;
    QTimer::singleShot(fallbackMs, this, [this, gen]() {
        if (gen != m_playbackGeneration) {
            return;
        }
        notifyPlaybackFinished();
    });
    return duration;
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

bool TTSManager::extractWavPcm(const QByteArray& wav, WavPcmInfo* out) const
{
    if (!out || wav.size() < 12) {
        return false;
    }
    const char* data = wav.constData();
    if (memcmp(data, "RIFF", 4) != 0 || memcmp(data + 8, "WAVE", 4) != 0) {
        return false;
    }

    int sampleRate = 0;
    int channelCount = 0;
    int bitsPerSample = 0;
    int pcmOffset = -1;
    quint32 pcmSize = 0;

    int offset = 12;
    while (offset + 8 <= wav.size()) {
        char chunkId[4];
        quint32 chunkSize = 0;
        memcpy(chunkId, data + offset, 4);
        memcpy(&chunkSize, data + offset + 4, 4);
        const int payload = offset + 8;
        if (payload > wav.size()) {
            break;
        }
        if (memcmp(chunkId, "fmt ", 4) == 0 && chunkSize >= 16 && payload + 16 <= wav.size()) {
            quint16 audioFormat = 0;
            quint16 channels = 0;
            quint32 rate = 0;
            quint16 bits = 0;
            memcpy(&audioFormat, data + payload, 2);
            memcpy(&channels, data + payload + 2, 2);
            memcpy(&rate, data + payload + 4, 4);
            memcpy(&bits, data + payload + 14, 2);
            Q_UNUSED(audioFormat);
            channelCount = channels;
            sampleRate = static_cast<int>(rate);
            bitsPerSample = bits;
        }
        else if (memcmp(chunkId, "data", 4) == 0) {
            pcmOffset = payload;
            pcmSize = chunkSize;
            break;
        }
        offset += 8 + static_cast<int>(chunkSize);
        if (chunkSize & 1) {
            offset += 1;
        }
    }

    if (pcmOffset < 0 || sampleRate <= 0 || channelCount <= 0 || bitsPerSample <= 0) {
        return false;
    }
    const int available = wav.size() - pcmOffset;
    const int bytes = qMin(static_cast<int>(pcmSize), available);
    if (bytes <= 0) {
        return false;
    }

    out->pcm = wav.mid(pcmOffset, bytes);
    out->sampleRate = sampleRate;
    out->channelCount = channelCount;
    out->bitsPerSample = bitsPerSample;
    out->durationSec = static_cast<double>(bytes)
        / (static_cast<double>(sampleRate) * channelCount * (bitsPerSample / 8.0));

    FINE_DEBUG_OUTPUT(QString("[TTS Operation]WAV file information: ")
        + "sample rate: " + QString::number(sampleRate)
        + "| channel num: " + QString::number(channelCount)
        + "| bits per sample: " + QString::number(bitsPerSample)
        + "| data size:" + QString::number(bytes)
        + "| duration:" + QString::number(out->durationSec) + " second");
    return true;
}

double TTSManager::getWavDuration(const QByteArray& audioData)
{
    WavPcmInfo info;
    if (!extractWavPcm(audioData, &info)) {
        ERROR_DEBUG_OUTPUT("[TTS Operation]Failed to find data");
        return -1;
    }
    return info.durationSec;
}

void TTSManager::processNextRequest()
{
    // 合成与播放解耦：只挡 HTTP 进行中，不挡正在播放
    if (isProcessingRequest || requestQueue.isEmpty()) {
        return;
    }

    isProcessingRequest = true;
    QueuedRequest request = requestQueue.dequeue();
    m_currentIsWarmup = (request.type == QueuedRequest::WarmupTTS);

    switch (request.type) {
    case QueuedRequest::TTSGet:
        executeTTSGet(request.params);
        break;
    case QueuedRequest::TTSPost:
    case QueuedRequest::WarmupTTS:
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
    case QueuedRequest::SetReferAudio:
        executeSetReferAudio(request.weightsPath);
        break;
    }
}

void TTSManager::executeTTSGet(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");
    url.setQuery(buildQueryFromParams(params));

    QNetworkRequest request(url);
    applyRequestTimeout(request);
    currentMediaType = params.mediaType;
    currentTtsText = params.text;
    currentTtsEmotion = params.emotion;

    cleanupCurrentReply();
    m_ttsRequestTimer.restart();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished,
        this, &TTSManager::onNetworkReplyFinished);
}

void TTSManager::executeTTSPost(const TTSRequestParams& params)
{
    QUrl url = buildBaseUrl();
    url.setPath("/tts");

    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    applyRequestTimeout(request);

    QJsonObject json = buildJsonFromParams(params);
    QJsonDocument doc(json);
    QByteArray data = doc.toJson();

    currentMediaType = params.mediaType;
    currentTtsText = params.text;
    currentTtsEmotion = params.emotion;

    cleanupCurrentReply();
    m_ttsRequestTimer.restart();
    currentReply = networkManager->post(request, data);

    connect(currentReply, &QNetworkReply::finished,
        this, &TTSManager::onNetworkReplyFinished);
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
    applyRequestTimeout(request);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (!currentReply) {
            emit modelSwitched(false, "GPT weight request aborted");
            isProcessingRequest = false;
            processNextRequest();
            return;
        }
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
            QString errorMsg = currentReply->errorString();
            if (currentReply->error() == QNetworkReply::TimeoutError
                || currentReply->error() == QNetworkReply::OperationCanceledError) {
                errorMsg = QString("GPT weight request timed out after %1 ms").arg(requestTimeoutMs);
            }
            emit modelSwitched(false, errorMsg);
        }

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
    applyRequestTimeout(request);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (!currentReply) {
            emit modelSwitched(false, "Sovits weight request aborted");
            isProcessingRequest = false;
            processNextRequest();
            return;
        }
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
            QString errorMsg = currentReply->errorString();
            if (currentReply->error() == QNetworkReply::TimeoutError
                || currentReply->error() == QNetworkReply::OperationCanceledError) {
                errorMsg = QString("Sovits weight request timed out after %1 ms").arg(requestTimeoutMs);
            }
            emit modelSwitched(false, errorMsg);
        }

        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        });
}

void TTSManager::executeSetReferAudio(const QString& audioPath)
{
    QUrl url = buildBaseUrl();
    url.setPath("/set_refer_audio");

    QUrlQuery query;
    query.addQueryItem("refer_audio_path", audioPath);
    url.setQuery(query);

    QNetworkRequest request(url);
    applyRequestTimeout(request);
    cleanupCurrentReply();
    currentReply = networkManager->get(request);

    connect(currentReply, &QNetworkReply::finished, [this]() {
        if (!currentReply) {
            ERROR_DEBUG_OUTPUT("[TTS Operation]set_refer_audio aborted");
            isProcessingRequest = false;
            processNextRequest();
            return;
        }
        if (currentReply->error() == QNetworkReply::NoError) {
            FINE_DEBUG_OUTPUT("[TTS Operation]set_refer_audio success");
        }
        else {
            ERROR_DEBUG_OUTPUT("[TTS Operation]set_refer_audio failed: " + currentReply->errorString());
        }

        cleanupCurrentReply();
        isProcessingRequest = false;
        processNextRequest();
        });
}
