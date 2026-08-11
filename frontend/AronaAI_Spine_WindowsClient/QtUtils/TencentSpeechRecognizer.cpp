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

#include "TencentSpeechRecognizer.h"
#include <QCryptographicHash>
#include <QMessageAuthenticationCode>
#include <QDateTime>
#include <QUrlQuery>
#include <QHttpMultiPart>
#include <QHttpPart>
#include <QFile>
#include <QBuffer>
#include <QRandomGenerator>

// 腾讯云语音识别API的固定参数
const QString SERVICE = "asr";
const QString ACTION = "SentenceRecognition"; // 一句话识别接口
const QString VERSION = "2019-06-14";
const QString REGION = "ap-guangzhou"; // 根据你的服务区域选择
const QString ENDPOINT = "asr.tencentcloudapi.com";

TencentSpeechRecognizer::TencentSpeechRecognizer(QObject* parent)
    : QObject(parent)
    , m_networkManager(new QNetworkAccessManager(this))
    , m_initialized(false)
{
    connect(m_networkManager, &QNetworkAccessManager::finished,
        this, &TencentSpeechRecognizer::onNetworkReplyFinished);
}

TencentSpeechRecognizer::~TencentSpeechRecognizer()
{
}

void TencentSpeechRecognizer::setCredentials(const QString& secretId, const QString& secretKey)
{
    m_secretId = secretId;
    m_secretKey = secretKey;
    m_initialized = !m_secretId.isEmpty() && !m_secretKey.isEmpty();
}

bool TencentSpeechRecognizer::isInitialized() const
{
    return m_initialized;
}

QString TencentSpeechRecognizer::recognize(const QByteArray& audioData)
{
    if (!m_initialized) {
        emit errorOccurred("[Tencent Speech Recognizer]TencentCloud authentication information havent beem set!");
        return QString();
    }

    if (audioData.isEmpty()) {
        emit errorOccurred("[Tencent Speech Recognizer]Audio data is null!");
        return QString();
    }

    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Start TencentCloud Speech Recoginizing...");
    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Audio data size: " + QString::number(audioData.size()) + "Bytes");

    // 1. 构建请求体
    QByteArray audioBase64 = audioData.toBase64();

    QJsonObject jsonBody;
    jsonBody["EngSerViceType"] = "16k_zh";
    jsonBody["SourceType"] = 1;
    jsonBody["VoiceFormat"] = "pcm";
    jsonBody["Data"] = QString(audioBase64);

    QJsonDocument jsonDoc(jsonBody);
    QByteArray requestBody = jsonDoc.toJson(QJsonDocument::Compact);

    // 2. 获取当前时间戳
    qint64 timestamp = QDateTime::currentSecsSinceEpoch();
    QString timestampStr = QString::number(timestamp);

    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Current timestamp: " + timestampStr);
    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Current time:" + QDateTime::fromSecsSinceEpoch(timestamp).toString("yyyy-MM-dd hh:mm:ss"));

    // 3. 生成签名
    QByteArray signature = generateSignature(SERVICE, ACTION, VERSION, REGION, requestBody, timestampStr);

    // 4. 构建请求 - ✅ 添加所有必要的头部
    QNetworkRequest request;
    request.setUrl(QUrl("https://" + ENDPOINT));
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json; charset=utf-8");
    request.setRawHeader("Host", ENDPOINT.toUtf8());
    request.setRawHeader("X-TC-Action", ACTION.toUtf8());
    request.setRawHeader("X-TC-Version", VERSION.toUtf8());
    request.setRawHeader("X-TC-Timestamp", timestampStr.toUtf8());
    request.setRawHeader("X-TC-Region", REGION.toUtf8());
    request.setRawHeader("X-TC-Language", "zh-CN");
    request.setRawHeader("Authorization", signature);

    m_networkManager->post(request, requestBody);

    return QString();
}

void TencentSpeechRecognizer::onNetworkReplyFinished(QNetworkReply* reply)
{
    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Get network reply succeed!");

    if (!reply) {
        // 无回复消息
        ERROR_DEBUG_OUTPUT("[Tencent Speech Recognizer]Network reply is null!");
        return;
    }

    reply->deleteLater();

    if (reply->error() != QNetworkReply::NoError) {
        // 网络请求失败
        ERROR_DEBUG_OUTPUT("[Tencent Speech Recognizer]Request failed!");
        emit errorOccurred("[Tencent Speech Recognizer]Request failed: " + reply->errorString());
        return;
    }

    // 读取响应数据
    QByteArray responseData = reply->readAll();
	// 输出原始返回数据用于调试
    FINE_DEBUG_OUTPUT("[Tencent Speech Recognizer]Raw response data: " + QString(responseData));

    // 解析 JSON
    QJsonParseError parseError;
    QJsonDocument jsonResponse = QJsonDocument::fromJson(responseData, &parseError);

    if (parseError.error != QJsonParseError::NoError) {
        emit errorOccurred("[Tencent Speech Recognizer]JSON analysis error: " + parseError.errorString());
        return;
    }

    if (!jsonResponse.isObject()) {
        emit errorOccurred("[Tencent Speech Recognizer]Response data is not JSON object!");
        return;
    }

    QJsonObject responseObj = jsonResponse.object();

    // 处理响应
    if (responseObj.contains("Response")) {
        QJsonObject resp = responseObj["Response"].toObject();
        if (resp.contains("Error")) {
            QJsonObject errorObj = resp["Error"].toObject();
            QString errorMsg = errorObj["Message"].toString();
            emit errorOccurred("[Tencent Speech Recognizer]TencentClout API error: " + errorMsg);
        }
        else {
            QString result = resp["Result"].toString().trimmed();
            if (result.isEmpty()) {
                // Empty ASR must not go through recognizeFinished → chat pipeline
                emit errorOccurred("[Tencent Speech Recognizer]Didnt recognize vailable content!");
            }
            else {
                emit recognizeFinished(result);
            }
        }
    }
    else {
        emit errorOccurred("[Tencent Speech Recognizer]Response data format error: lack of 'Response'");
    }
}

// 生成腾讯云API v3签名 (这是最复杂的部分，需要严格按照腾讯云文档实现)
QByteArray TencentSpeechRecognizer::generateSignature(const QString& service, const QString& action,
    const QString& version, const QString& region,
    const QByteArray& payload, const QString& timestamp)
{
    QString algorithm = "TC3-HMAC-SHA256";

    // 1. 构建 CanonicalRequest
    QString httpRequestMethod = "POST";
    QString canonicalUri = "/";
    QString canonicalQueryString = "";
    QString actionLower = action.toLower();
    QString canonicalHeaders = QString("content-type:application/json; charset=utf-8\n") +
        "host:" + ENDPOINT + "\n" +
        "x-tc-action:" + actionLower + "\n";
    QString signedHeaders = "content-type;host;x-tc-action";  // ✅ 添加 x-tc-action

    QByteArray hashedRequestPayload = QCryptographicHash::hash(payload, QCryptographicHash::Sha256).toHex();
    QString canonicalRequest = httpRequestMethod + "\n" +
        canonicalUri + "\n" +
        canonicalQueryString + "\n" +
        canonicalHeaders + "\n" +
        signedHeaders + "\n" +
        hashedRequestPayload;

    // 构建 StringToSign
    QByteArray hashedCanonicalRequest = QCryptographicHash::hash(canonicalRequest.toUtf8(), QCryptographicHash::Sha256).toHex();
    QString date = QDateTime::fromSecsSinceEpoch(timestamp.toLongLong()).toString("yyyy-MM-dd");
    QString credentialScope = date + "/" + service + "/tc3_request";
    QString stringToSign = algorithm + "\n" +
        timestamp + "\n" +
        credentialScope + "\n" +
        hashedCanonicalRequest;

    // 计算签名
    QByteArray secretKeyBytes = m_secretKey.toUtf8();

    // kKey = "TC3" + SecretKey
    QByteArray kKey = "TC3" + secretKeyBytes;

    // kDate = HMAC_SHA256(kKey, Date)
    QByteArray kDate = hmacSha256(kKey, date.toUtf8());

    // kService = HMAC_SHA256(kDate, Service)
    QByteArray kService = hmacSha256(kDate, service.toUtf8());

    // kSigning = HMAC_SHA256(kService, "tc3_request")
    QByteArray kSigning = hmacSha256(kService, "tc3_request");

    // Signature = HexEncode(HMAC_SHA256(kSigning, StringToSign))
    QByteArray signature = hexEncode(hmacSha256(kSigning, stringToSign.toUtf8()));

    // 4. 构建 Authorization
    QString authorization = algorithm + " " +
        "Credential=" + m_secretId + "/" + credentialScope + ", " +
        "SignedHeaders=" + signedHeaders + ", " +
        "Signature=" + signature;

    return authorization.toUtf8();
}

// 返回原始的二进制数据（不是十六进制）
QByteArray TencentSpeechRecognizer::hmacSha256(const QByteArray& key, const QByteArray& data)
{
    return QMessageAuthenticationCode::hash(data, key, QCryptographicHash::Sha256);
    // 注意：QMessageAuthenticationCode::hash 返回的是原始二进制数据！
}

// 将二进制数据转换为十六进制字符串
QByteArray TencentSpeechRecognizer::hexEncode(const QByteArray& input)
{
    return input.toHex();
}