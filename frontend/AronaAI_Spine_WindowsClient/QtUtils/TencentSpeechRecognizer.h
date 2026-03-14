#ifndef TENCENTSPEECHRECOGNIZER_H
#define TENCENTSPEECHRECOGNIZER_H

#include "Defines.h"

#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QUrl>
#include <QByteArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QElapsedTimer> // 用于生成请求中的随机数

class TencentSpeechRecognizer : public QObject
{
    Q_OBJECT

public:
    explicit TencentSpeechRecognizer(QObject* parent = nullptr);
    ~TencentSpeechRecognizer();
    // 设置腾讯云的认证信息 (可以从配置文件或环境变量读取)
    void setCredentials(const QString& secretId, const QString& secretKey);
    // 识别音频数据 (对外接口，与之前保持一致)
    QString recognize(const QByteArray& audioData);
    // 检查是否已设置认证信息
    bool isInitialized() const;
    // 返回原始的二进制数据
    QByteArray hmacSha256(const QByteArray& key, const QByteArray& data);
    // 将二进制数据转换为十六进制字符串
    QByteArray hexEncode(const QByteArray& input);

signals:
    void errorOccurred(const QString& error);
    void recognizeFinished(const QString& result); // 识别完成时发出的信号

private slots:
    void onNetworkReplyFinished(QNetworkReply* reply); // 处理网络回复

private:
    // 生成腾讯云API v3签名
    QByteArray generateSignature(const QString& service, const QString& action,
        const QString& version, const QString& region,
        const QByteArray& payload, const QString& timestamp);

    QString m_secretId;
    QString m_secretKey;
    QNetworkAccessManager* m_networkManager;
    bool m_initialized;
};

#endif // TENCENTSPEECHRECOGNIZER_H