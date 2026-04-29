// WebSocketController.cpp
#include "WebSocketController.h"
#include <QDebug>
#include <QJsonArray>
#include <QDateTime>

WebSocketController::WebSocketController(QObject* parent)
    : QObject(parent)
    , m_webSocket(new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this))
    , m_heartbeatTimer(new QTimer(this))
    , m_heartbeatCheckTimer(new QTimer(this))
    , m_reconnectTimer(new QTimer(this))
    , m_currentState(ConnectionState::Disconnected)
    , m_serverUrl(GET_STRING_FROM_JSON(_global_config, "aronalm", "websocket_url")) // websocket地址
    , m_heartbeatInterval(GET_INT_FROM_JSON(_global_config, "aronalm", "heartbeat_interval"))   // 心跳间隔
    , m_heartbeatTimeout(GET_INT_FROM_JSON(_global_config, "aronalm", "heartbeat_timeout")) // 心跳超时
    , m_reconnectInterval(GET_INT_FROM_JSON(_global_config, "aronalm", "reconnect_interval"))   // 重连间隔
    , m_maxReconnectAttempts(GET_INT_FROM_JSON(_global_config, "aronalm", "max_reconnect_attempts"))    // 最多重连
    , m_currentReconnectCount(0)
    , m_autoReconnect(true)
    , m_pongReceived(false)
    , m_cacheMessages(true)
{
    // 连接WebSocket信号
    connect(m_webSocket, &QWebSocket::connected, this, [this]() {
        onConnected();
        });
    connect(m_webSocket, &QWebSocket::disconnected,
        this, &WebSocketController::onDisconnected);
    connect(m_webSocket, &QWebSocket::textMessageReceived,
        this, &WebSocketController::onTextMessageReceived);

    // Qt 6.5+ 使用 errorOccurred，之前版本使用 error
#if QT_VERSION >= QT_VERSION_CHECK(6, 5, 0)
    connect(m_webSocket, &QWebSocket::errorOccurred, this,
        [this](QAbstractSocket::SocketError error) {
            onError(error);
        });
#else
    connect(m_webSocket, QOverload<QAbstractSocket::SocketError>::of(&QWebSocket::error),
        this, &WebSocketController::onError);
#endif

    // 心跳计时器
    connect(m_heartbeatTimer, &QTimer::timeout,
        this, &WebSocketController::onHeartbeatTimer);

    // 心跳检查计时器（单次触发）
    m_heartbeatCheckTimer->setSingleShot(true);
    connect(m_heartbeatCheckTimer, &QTimer::timeout,
        this, &WebSocketController::onHeartbeatCheckTimer);

    // 重连计时器
    connect(m_reconnectTimer, &QTimer::timeout,
        this, &WebSocketController::onReconnectTimer);
}

WebSocketController::~WebSocketController()
{
    stopHeartbeat();
    stopReconnect();

    if (m_webSocket->state() == QAbstractSocket::ConnectedState) {
        m_webSocket->close();
    }
}

// ========== 连接管理实现 ==========

void WebSocketController::connectToServer()
{
    if (m_serverUrl.isEmpty()) {
        emit errorOccurred(ErrorCode::ConnectionRefused, "服务器URL未设置");
        if (m_onErrorOccurredCallback) {
            m_onErrorOccurredCallback(ErrorCode::ConnectionRefused, "服务器URL未设置");
        }
        return;
    }

    if (m_currentState == ConnectionState::Connected ||
        m_currentState == ConnectionState::Connecting) {
        qDebug() << "WebSocketController: 已经连接或正在连接";
        return;
    }

    setState(ConnectionState::Connecting);

    qDebug() << "WebSocketController: 正在连接到" << m_serverUrl;
    m_webSocket->open(QUrl(m_serverUrl));
}

void WebSocketController::disconnectFromServer()
{
    m_autoReconnect = false;  // 手动断开时不自动重连
    stopHeartbeat();
    stopReconnect();

    if (m_webSocket->state() == QAbstractSocket::ConnectedState) {
        m_webSocket->close();
    }

    setState(ConnectionState::Disconnected);
    m_currentReconnectCount = 0;
}

WebSocketController::ConnectionState WebSocketController::state() const
{
    return m_currentState;
}

bool WebSocketController::isConnected() const
{
    return m_currentState == ConnectionState::Connected;
}

// ========== 配置实现 ==========

void WebSocketController::setServerUrl(const QString& url)
{
    m_serverUrl = url;
}

void WebSocketController::setHeartbeatInterval(int intervalMs)
{
    m_heartbeatInterval = intervalMs;
}

void WebSocketController::setHeartbeatTimeout(int timeoutMs)
{
    m_heartbeatTimeout = timeoutMs;
}

void WebSocketController::setReconnectInterval(int intervalMs)
{
    m_reconnectInterval = intervalMs;
}

void WebSocketController::setMaxReconnectAttempts(int attempts)
{
    m_maxReconnectAttempts = attempts;
}

void WebSocketController::setAutoReconnect(bool enabled)
{
    m_autoReconnect = enabled;
}

// ========== 消息发送实现 ==========

void WebSocketController::sendChatMessage(const QString& content,
    bool useCache, bool useRag, bool useMemory)
{
    QJsonObject message;
    message["type"] = "chat";
    message["content"] = content;
    message["stream"] = false;

    QJsonObject options;
    options["use_cache"] = useCache;
    options["use_rag"] = useRag;
    options["use_memory"] = useMemory;
    message["options"] = options;

    sendMessage(message);
}

void WebSocketController::sendStreamChatMessage(const QString& content,
    bool useCache, bool useRag, bool useMemory)
{
    QJsonObject message;
    message["type"] = "chat";
    message["content"] = content;
    message["stream"] = true;

    QJsonObject options;
    options["use_cache"] = useCache;
    options["use_rag"] = useRag;
    options["use_memory"] = useMemory;
    message["options"] = options;

    sendMessage(message);
}

void WebSocketController::clearSession()
{
    QJsonObject message;
    message["type"] = "clear_session";
    sendMessage(message);
}

void WebSocketController::getStats()
{
    QJsonObject message;
    message["type"] = "get_stats";
    sendMessage(message);
}

void WebSocketController::sendPing()
{
    QJsonObject message;
    message["type"] = "ping";
    sendMessage(message);
}

void WebSocketController::sendMessage(const QJsonObject& message)
{
    if (m_currentState == ConnectionState::Connected) {
        sendJsonMessage(message);
    }
    else if (m_cacheMessages) {
        // 未连接时缓存消息（队列最多缓存100条）
        if (m_messageQueue.size() < 100) {
            m_messageQueue.enqueue(message);
            qDebug() << "WebSocketController: 消息已缓存，队列大小:" << m_messageQueue.size();
        }
        else {
            qWarning() << "WebSocketController: 消息队列已满，丢弃消息";
        }
    }
    else {
        qWarning() << "WebSocketController: 未连接，无法发送消息";
    }
}

void WebSocketController::sendJsonMessage(const QJsonObject& message)
{
    QJsonDocument doc(message);
    QString jsonString = doc.toJson(QJsonDocument::Compact);
    m_webSocket->sendTextMessage(jsonString);
}

// ========== 回调注册实现 ==========

void WebSocketController::onMessageReceived(MessageCallback callback)
{
    m_onMessageCallback = callback;
}

void WebSocketController::onChatResponse(MessageCallback callback)
{
    m_onChatResponseCallback = callback;
}

void WebSocketController::onChatStream(MessageCallback callback)
{
    m_onChatStreamCallback = callback;
}

void WebSocketController::onError(ErrorCallback callback)
{
    m_onErrorCallback = callback;
}

void WebSocketController::onConnectionStateChanged(StateCallback callback)
{
    m_onStateChangedCallback = callback;
}

void WebSocketController::onConnected(MessageCallback callback)
{
    m_onConnectedCallback = callback;
}

void WebSocketController::onStatsReceived(MessageCallback callback)
{
    m_onStatsCallback = callback;
}

void WebSocketController::onResult(MessageCallback callback)
{
    m_onResultCallback = callback;
}

void WebSocketController::onPong(MessageCallback callback)
{
    m_onPongCallback = callback;
}

void WebSocketController::onErrorOccurred(ErrorCallback callback)
{
    m_onErrorOccurredCallback = callback;
}

// ========== 内部槽函数实现 ==========

void WebSocketController::onConnected()
{
    qDebug() << "WebSocketController: 已连接到服务器";
    setState(ConnectionState::Connected);
    m_currentReconnectCount = 0;
    m_pongReceived = true;

    // 启动心跳
    startHeartbeat();

    // 发送缓存的消息
    while (!m_messageQueue.isEmpty() && m_currentState == ConnectionState::Connected) {
        QJsonObject message = m_messageQueue.dequeue();
        sendJsonMessage(message);
    }
}

void WebSocketController::onDisconnected()
{
    qDebug() << "WebSocketController: 与服务器断开连接";
    stopHeartbeat();

    if (m_currentState == ConnectionState::Connected) {
        setState(ConnectionState::Disconnected);
        emit disconnected();

        // 自动重连
        if (m_autoReconnect) {
            startReconnect();
        }
    }
}

void WebSocketController::onTextMessageReceived(const QString& message)
{
    QJsonParseError error;
    QJsonDocument doc = QJsonDocument::fromJson(message.toUtf8(), &error);

    if (error.error != QJsonParseError::NoError) {
        qWarning() << "WebSocketController: JSON解析错误:" << error.errorString();
        emit errorOccurred(ErrorCode::InvalidMessage, "无效的JSON格式: " + error.errorString());
        return;
    }

    if (!doc.isObject()) {
        qWarning() << "WebSocketController: 消息不是JSON对象";
        return;
    }

    QJsonObject jsonObj = doc.object();

    // 重置心跳超时计时器（收到任何消息都视为连接活跃）
    resetHeartbeatTimer();

    // 处理消息
    handleMessage(jsonObj);

    // 触发通用消息回调
    if (m_onMessageCallback) {
        m_onMessageCallback(jsonObj);
    }

    emit messageReceived(jsonObj);
}

void WebSocketController::onError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error)
        QString errorMsg = m_webSocket->errorString();
    qWarning() << "WebSocketController: WebSocket错误:" << errorMsg;

    emit errorOccurred(ErrorCode::NetworkError, errorMsg);

    if (m_onErrorOccurredCallback) {
        m_onErrorOccurredCallback(ErrorCode::NetworkError, errorMsg);
    }
}

void WebSocketController::onHeartbeatTimer()
{
    if (m_currentState == ConnectionState::Connected) {
        // 检查上一次心跳是否收到响应
        if (!m_pongReceived) {
            qWarning() << "WebSocketController: 心跳超时，未收到pong响应";
            emit heartbeatTimeout();

            // 断开连接并重连
            m_webSocket->close();
            return;
        }

        // 发送心跳
        m_pongReceived = false;
        sendPing();

        // 启动心跳超时检查
        m_heartbeatCheckTimer->start(m_heartbeatTimeout);
    }
}

void WebSocketController::onHeartbeatCheckTimer()
{
    if (!m_pongReceived) {
        qWarning() << "WebSocketController: 心跳检查超时";
        emit heartbeatTimeout();

        // 断开连接并重连
        m_webSocket->close();
    }
}

void WebSocketController::onReconnectTimer()
{
    if (m_currentState == ConnectionState::Connected ||
        m_currentState == ConnectionState::Connecting) {
        return;
    }

    if (m_maxReconnectAttempts != -1 &&
        m_currentReconnectCount >= m_maxReconnectAttempts) {
        qWarning() << "WebSocketController: 达到最大重连次数，停止重连";
        stopReconnect();

        emit errorOccurred(ErrorCode::ReconnectFailed,
            QString("重连失败，已尝试%1次").arg(m_currentReconnectCount));
        if (m_onErrorOccurredCallback) {
            m_onErrorOccurredCallback(ErrorCode::ReconnectFailed,
                QString("重连失败，已尝试%1次").arg(m_currentReconnectCount));
        }
        return;
    }

    m_currentReconnectCount++;
    qDebug() << "WebSocketController: 尝试重连 (" << m_currentReconnectCount << "/"
        << (m_maxReconnectAttempts == -1 ? "∞" : QString::number(m_maxReconnectAttempts)) << ")";

    setState(ConnectionState::Reconnecting);
    m_webSocket->open(QUrl(m_serverUrl));
}

void WebSocketController::onPongReceived()
{
    m_pongReceived = true;
    m_heartbeatCheckTimer->stop();
}

// ========== 消息处理实现 ==========

void WebSocketController::handleMessage(const QJsonObject& message)
{
    QString type = message["type"].toString();

    if (type == "chat_response") {
        handleChatResponse(message);
    }
    else if (type == "chat_stream") {
        handleChatStream(message);
    }
    else if (type == "error") {
        handleError(message);
    }
    else if (type == "connected") {
        handleConnected(message);
    }
    else if (type == "stats") {
        handleStats(message);
    }
    else if (type == "result") {
        handleResult(message);
    }
    else if (type == "pong") {
        handlePong(message);
    }
    else {
        qDebug() << "WebSocketController: 未知消息类型:" << type;
    }
}

void WebSocketController::handleChatResponse(const QJsonObject& message)
{
    QString content = message["content"].toString();
    bool fromCache = message["from_cache"].toBool(false);
    bool contextUsed = message["context_used"].toBool(false);
    double latency = message["latency"].toDouble(0.0);

    qDebug() << "WebSocketController: 收到聊天响应:" << content.left(50) << "...";

    emit chatResponseReceived(content, fromCache, contextUsed, latency);

    if (m_onChatResponseCallback) {
        m_onChatResponseCallback(message);
    }
}

void WebSocketController::handleChatStream(const QJsonObject& message)
{
    bool done = message["done"].toBool(false);
    QString content = message["content"].toString();

    if (done) {
        // 流式传输完成
        qDebug() << "WebSocketController: 流式传输完成";
        m_streamBuffer.clear();
    }
    else {
        // 累积流式内容
        m_streamBuffer += content;
    }

    emit chatStreamReceived(content, done);

    if (m_onChatStreamCallback) {
        m_onChatStreamCallback(message);
    }
}

void WebSocketController::handleError(const QJsonObject& message)
{
    QString code = message["code"].toString();
    QString errorMsg = message["message"].toString();

    qWarning() << "WebSocketController: 服务器错误:" << code << "-" << errorMsg;

    ErrorCode errorCode = ErrorCode::ProtocolError;
    if (code == "INVALID_JSON") errorCode = ErrorCode::InvalidMessage;

    emit errorOccurred(errorCode, errorMsg);

    if (m_onErrorCallback) {
        m_onErrorCallback(errorCode, errorMsg);
    }
}

void WebSocketController::handleConnected(const QJsonObject& message)
{
    QString sessionId = message["session_id"].toString();
    qDebug() << "WebSocketController: 会话已建立，session_id:" << sessionId;

    emit connected(sessionId);

    if (m_onConnectedCallback) {
        m_onConnectedCallback(message);
    }
}

void WebSocketController::handleStats(const QJsonObject& message)
{
    qDebug() << "WebSocketController: 收到统计信息";

    if (m_onStatsCallback) {
        m_onStatsCallback(message);
    }
}

void WebSocketController::handleResult(const QJsonObject& message)
{
    bool success = message["success"].toBool();
    QString resultMsg = message["message"].toString();
    qDebug() << "WebSocketController: 操作结果 - 成功:" << success << " 消息:" << resultMsg;

    if (m_onResultCallback) {
        m_onResultCallback(message);
    }
}

void WebSocketController::handlePong(const QJsonObject& message)
{
    qDebug() << "WebSocketController: 收到pong响应";
    onPongReceived();

    if (m_onPongCallback) {
        m_onPongCallback(message);
    }
}

// ========== 心跳管理实现 ==========

void WebSocketController::startHeartbeat()
{
    stopHeartbeat();
    m_pongReceived = true;
    m_heartbeatTimer->start(m_heartbeatInterval);
    qDebug() << "WebSocketController: 心跳已启动，间隔:" << m_heartbeatInterval << "ms";
}

void WebSocketController::stopHeartbeat()
{
    m_heartbeatTimer->stop();
    m_heartbeatCheckTimer->stop();
    qDebug() << "WebSocketController: 心跳已停止";
}

void WebSocketController::resetHeartbeatTimer()
{
    if (m_currentState == ConnectionState::Connected) {
        m_pongReceived = true;
        m_heartbeatCheckTimer->stop();
        // 重置心跳发送计时器
        m_heartbeatTimer->start(m_heartbeatInterval);
    }
}

// ========== 重连管理实现 ==========

void WebSocketController::startReconnect()
{
    if (!m_reconnectTimer->isActive()) {
        m_reconnectTimer->start(m_reconnectInterval);
        qDebug() << "WebSocketController: 开始重连，间隔:" << m_reconnectInterval << "ms";
    }
}

void WebSocketController::stopReconnect()
{
    m_reconnectTimer->stop();
    m_currentReconnectCount = 0;
    qDebug() << "WebSocketController: 停止重连";
}

void WebSocketController::setState(ConnectionState newState)
{
    if (m_currentState != newState) {
        m_currentState = newState;

        QString stateStr;
        switch (newState) {
        case ConnectionState::Disconnected: stateStr = "Disconnected"; break;
        case ConnectionState::Connecting: stateStr = "Connecting"; break;
        case ConnectionState::Connected: stateStr = "Connected"; break;
        case ConnectionState::Reconnecting: stateStr = "Reconnecting"; break;
        }
        qDebug() << "WebSocketController: 状态变更 ->" << stateStr;

        emit connectionStateChanged(newState);

        if (m_onStateChangedCallback) {
            m_onStateChangedCallback(newState);
        }
    }
}