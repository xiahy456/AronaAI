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

    qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Start TencentCloud Speech Recoginizing...";
    qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Audio data size: " << audioData.size() << "Bytes";

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

    qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Current timestamp: " << timestampStr;
    qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Current time:" << QDateTime::fromSecsSinceEpoch(timestamp).toString("yyyy-MM-dd hh:mm:ss");

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

    // 发送请求
    //qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Sent request to: " << request.url().toString();
    //qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Request head: ";
    //for (const auto& header : request.rawHeaderList()) {
    //    qDebug() << "  " << header << ":" << request.rawHeader(header);
    //}
    //qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Request body: " << requestBody;

    m_networkManager->post(request, requestBody);

    return QString();
}

void TencentSpeechRecognizer::onNetworkReplyFinished(QNetworkReply* reply)
{
	qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Get network reply succeed!";

    if (!reply) {
        // 无回复消息
		qWarning().noquote() << ERROR_PR << "[Tencent Speech Recognizer]Network reply is null!";
        return;
    }

    reply->deleteLater();

    if (reply->error() != QNetworkReply::NoError) {
        // 网络请求失败
        qWarning().noquote() << ERROR_PR << "[Tencent Speech Recognizer]Request failed!";
        emit errorOccurred("[Tencent Speech Recognizer]Request failed: " + reply->errorString());
        return;
    }

    // 读取响应数据
    QByteArray responseData = reply->readAll();
	// 输出原始返回数据用于调试
	qDebug().noquote() << FINE_PR << "[Tencent Speech Recognizer]Raw response data: " << QString(responseData);

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
            QString result = resp["Result"].toString();
            if (result.isEmpty()) {
                // 可能是部分识别结果或其他格式
                emit recognizeFinished("[Tencent Speech Recognizer]Didnt recognize vailable content!");
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

    // ✅ 修正：必须包含 x-tc-action，且值必须是小写
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

    // 2. 构建 StringToSign
    QByteArray hashedCanonicalRequest = QCryptographicHash::hash(canonicalRequest.toUtf8(), QCryptographicHash::Sha256).toHex();
    QString date = QDateTime::fromSecsSinceEpoch(timestamp.toLongLong()).toString("yyyy-MM-dd");
    QString credentialScope = date + "/" + service + "/tc3_request";
    QString stringToSign = algorithm + "\n" +
        timestamp + "\n" +
        credentialScope + "\n" +
        hashedCanonicalRequest;

    // 3. 计算签名 - ✅ 严格按照官方示例
    QByteArray secretKeyBytes = m_secretKey.toUtf8();

    // kKey = "TC3" + SecretKey
    QByteArray kKey = "TC3" + secretKeyBytes;

    // kDate = HMAC_SHA256(kKey, Date)  ✅ 返回二进制
    QByteArray kDate = hmacSha256(kKey, date.toUtf8());

    // kService = HMAC_SHA256(kDate, Service)  ✅ kDate 是二进制
    QByteArray kService = hmacSha256(kDate, service.toUtf8());

    // kSigning = HMAC_SHA256(kService, "tc3_request")  ✅ kService 是二进制
    QByteArray kSigning = hmacSha256(kService, "tc3_request");

    // Signature = HexEncode(HMAC_SHA256(kSigning, StringToSign))  ✅ 只在最后一步转十六进制
    QByteArray signature = hexEncode(hmacSha256(kSigning, stringToSign.toUtf8()));

    // 4. 构建 Authorization
    QString authorization = algorithm + " " +
        "Credential=" + m_secretId + "/" + credentialScope + ", " +
        "SignedHeaders=" + signedHeaders + ", " +
        "Signature=" + signature;

    // 调试输出
    //qDebug() << "\n=== 签名验证信息 ===";
    //qDebug() << "SecretId:" << m_secretId;
    //qDebug() << "Date:" << date;
    //qDebug() << "CredentialScope:" << credentialScope;
    //qDebug() << "CanonicalHeaders:\n" << canonicalHeaders;
    //qDebug() << "CanonicalRequest:\n" << canonicalRequest;
    //qDebug() << "StringToSign:\n" << stringToSign;
    //qDebug() << "kDate (hex):" << kDate.toHex();
    //qDebug() << "kService (hex):" << kService.toHex();
    //qDebug() << "kSigning (hex):" << kSigning.toHex();
    //qDebug() << "Final Signature:" << signature;
    //qDebug() << "Authorization:" << authorization;
    //qDebug() << "===================\n";

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