#ifndef TTSMANAGER_H
#define TTSMANAGER_H

#include "Defines.h"
#include "JsonOperation.h"
#include "GlobalVariables.h"

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QUrl>
#include <QUrlQuery>
#include <QJsonObject>
#include <QJsonDocument>
#include <QFile>
#include <QAudioOutput>
#include <QBuffer>
#include <QAudioFormat>
#include <QJsonArray>
#include <QMediaDevices>
#include <QAudioSink>

class TTSManager : public QObject
{
    Q_OBJECT

public:
    explicit TTSManager(QObject* parent = nullptr);
    ~TTSManager();

    // 设置服务器地址
    void setServerAddress(const QString& host, int port);

    // TTS请求参数结构体
    struct TTSRequestParams {
        QString text = "";  // 要合成的文本
        QString textLang = "zh";    // 文本语言
        QString refAudioPath = "";  // 参考音频路径
        QStringList auxRefAudioPaths;   // 辅助参考音频路径
        QString promptText = "";    // 提示文本
        QString promptLang = "zh";  // 提示文本语言
        int topK = 5;   // top k采样
        double topP = 1.0;  // top p采样
        double temperature = 1.0;   // 温度参数
        QString textSplitMethod = "cut0";   // 文本分割方法
        int batchSize = 1;  // 批处理大小
        double batchThreshold = 0.75;   // 批处理阈值
        bool splitBucket = true;    // 是否分割桶
        double speedFactor = 1.0;   // 语速因子
        double fragmentInterval = 0.3;  // 片段间隔
        int seed = -1;  // 随机种子
        bool streamingMode = false; // 流式模式
        bool parallelInfer = true;  // 并行推理
        double repetitionPenalty = 1.35;    // 重复惩罚
        int sampleSteps = 32;   // 采样步数
        bool superSampling = false; // 超采样
        QString mediaType = "wav";  // 媒体类型
    };

    // 发送TTS请求（GET方式）
    void requestTTSGet(const TTSRequestParams& params);

    // 发送TTS请求（POST方式）
    void requestTTSPost(const TTSRequestParams& params);

    // 控制命令
    void sendControlCommand(const QString& command);

    // 设置GPT模型
    void setGPTWeights(const QString& weightsPath);

    // 设置Sovits模型
    void setSovitsWeights(const QString& weightsPath);

    // 播放音频
    void playAudio(const QByteArray& audioData);

    // 保存音频到文件
    bool saveAudioToFile(const QByteArray& audioData, const QString& filePath);

signals:
    // TTS完成信号
    void ttsFinished(const QByteArray& audioData, const QString& mediaType);
    // TTS流式数据接收信号
    void ttsChunkReceived(const QByteArray& chunkData);
    // TTS错误信号
    void ttsError(const QString& errorString);
    // 命令执行完成信号
    void commandFinished(bool success, const QString& message);
    // 模型切换完成信号
    void modelSwitched(bool success, const QString& message);

private slots:
    void onNetworkReplyFinished();
    void onStreamReadyRead();
    void onStreamFinished();

private:
	TTSRequestParams ttsRequestParams;
    QNetworkAccessManager* networkManager;
    QString serverHost;
    int serverPort;

    QNetworkReply* currentReply;
    QByteArray accumulatedAudioData;
    QString currentMediaType;

    QAudioSink* audioSink;
    QBuffer* audioBuffer;

    QUrl buildBaseUrl() const;
    QUrlQuery buildQueryFromParams(const TTSRequestParams& params) const;
    QJsonObject buildJsonFromParams(const TTSRequestParams& params) const;
    void handleTTSResponse(QNetworkReply* reply);

};

#endif // TTSMANAGER_H