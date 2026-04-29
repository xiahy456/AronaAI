#pragma once
#ifndef WEBSOCKETCONTROLLER_H
#define WEBSOCKETCONTROLLER_H

#include "Defines.h"
#include <GlobalInclude.h>

#include <QObject>
#include <QWebSocket>
#include <QTimer>
#include <QJsonObject>
#include <QJsonDocument>
#include <QQueue>
#include <functional>

class WebSocketController : public QObject
{
    Q_OBJECT

public:
    // 连接状态枚举
    enum class ConnectionState {
        Disconnected,
        Connecting,
        Connected,
        Reconnecting
    };
    Q_ENUM(ConnectionState)

        // 错误码枚举
        enum class ErrorCode {
        NoError,
        ConnectionRefused,
        ConnectionTimeout,
        NetworkError,
        ProtocolError,
        HeartbeatTimeout,
        ReconnectFailed,
        InvalidMessage
    };
    Q_ENUM(ErrorCode)

        // 回调函数类型定义
        using MessageCallback = std::function<void(const QJsonObject&)>;
    using ErrorCallback = std::function<void(ErrorCode, const QString&)>;
    using StateCallback = std::function<void(ConnectionState)>;

    explicit WebSocketController(QObject* parent = nullptr);
    ~WebSocketController();

    // ========== 连接管理接口 ==========

    // 连接到服务器
    void connectToServer();

    // 断开连接
    void disconnectFromServer();

    // 获取当前连接状态
    ConnectionState state() const;

    // 是否已连接
    bool isConnected() const;

    // ========== 配置接口 ==========

    // 设置服务器URL
    void setServerUrl(const QString& url);

    // 设置心跳间隔（毫秒），默认30000ms
    void setHeartbeatInterval(int intervalMs);

    // 设置心跳超时时间（毫秒），默认10000ms
    void setHeartbeatTimeout(int timeoutMs);

    // 设置重连间隔（毫秒），默认3000ms
    void setReconnectInterval(int intervalMs);

    // 设置最大重连次数，-1表示无限重连，默认5次
    void setMaxReconnectAttempts(int attempts);

    // 启用/禁用自动重连
    void setAutoReconnect(bool enabled);

    // ========== 消息发送接口 ==========

    // 发送聊天消息（非流式）
    void sendChatMessage(const QString& content,
        bool useCache = true,
        bool useRag = true,
        bool useMemory = true);

    // 发送聊天消息（流式）
    void sendStreamChatMessage(const QString& content,
        bool useCache = true,
        bool useRag = true,
        bool useMemory = true);

    // 清空会话
    void clearSession();

    // 获取统计信息
    void getStats();

    // 发送心跳
    void sendPing();

    // 发送自定义消息
    void sendMessage(const QJsonObject& message);

    // ========== 回调注册接口 ==========

    // 注册消息回调
    void onMessageReceived(MessageCallback callback);

    // 注册特定类型消息回调
    void onChatResponse(MessageCallback callback);
    void onChatStream(MessageCallback callback);
    void onError(ErrorCallback callback);
    void onConnectionStateChanged(StateCallback callback);
    void onConnected(MessageCallback callback);
    void onStatsReceived(MessageCallback callback);
    void onResult(MessageCallback callback);
    void onPong(MessageCallback callback);

    // 通用错误回调
    void onErrorOccurred(ErrorCallback callback);

signals:
    // 连接状态变化信号
    void connectionStateChanged(ConnectionState state);

    // 收到消息信号
    void messageReceived(const QJsonObject& message);

    // 收到聊天响应信号
    void chatResponseReceived(const QString& content, bool fromCache,
        bool contextUsed, double latency);

    // 收到流式聊天片段信号
    void chatStreamReceived(const QString& content, bool done);

    // 收到错误信号
    void errorOccurred(ErrorCode code, const QString& message);

    // 连接成功信号
    void connected(const QString& sessionId);

    // 断开连接信号
    void disconnected();

    // 心跳超时信号
    void heartbeatTimeout();

private slots:
    void onConnected();
    void onDisconnected();
    void onTextMessageReceived(const QString& message);
    void onError(QAbstractSocket::SocketError error);
    void onHeartbeatTimer();
    void onHeartbeatCheckTimer();
    void onReconnectTimer();
    void onPongReceived();

private:
    // 发送JSON消息
    void sendJsonMessage(const QJsonObject& message);

    // 处理接收到的消息
    void handleMessage(const QJsonObject& message);

    // 处理聊天响应
    void handleChatResponse(const QJsonObject& message);

    // 处理流式聊天
    void handleChatStream(const QJsonObject& message);

    // 处理错误
    void handleError(const QJsonObject& message);

    // 处理连接成功
    void handleConnected(const QJsonObject& message);

    // 处理统计信息
    void handleStats(const QJsonObject& message);

    // 处理操作结果
    void handleResult(const QJsonObject& message);

    // 处理心跳响应
    void handlePong(const QJsonObject& message);

    // 开始心跳
    void startHeartbeat();

    // 停止心跳
    void stopHeartbeat();

    // 开始重连
    void startReconnect();

    // 停止重连
    void stopReconnect();

    // 重置心跳计时器
    void resetHeartbeatTimer();

    // 设置连接状态
    void setState(ConnectionState newState);

private:
    QWebSocket* m_webSocket;
    QTimer* m_heartbeatTimer;
    QTimer* m_heartbeatCheckTimer;
    QTimer* m_reconnectTimer;

    QString m_serverUrl;
    ConnectionState m_currentState;

    // 配置参数
    int m_heartbeatInterval;      // 心跳发送间隔（ms）
    int m_heartbeatTimeout;       // 心跳超时时间（ms）
    int m_reconnectInterval;      // 重连间隔（ms）
    int m_maxReconnectAttempts;   // 最大重连次数，-1表示无限
    int m_currentReconnectCount;  // 当前重连次数
    bool m_autoReconnect;         // 是否自动重连
    bool m_pongReceived;         // 是否收到pong响应

    // 消息队列（未连接时缓存消息）
    QQueue<QJsonObject> m_messageQueue;
    bool m_cacheMessages;         // 是否缓存消息

    // 回调函数
    MessageCallback m_onMessageCallback;
    MessageCallback m_onChatResponseCallback;
    MessageCallback m_onChatStreamCallback;
    ErrorCallback m_onErrorCallback;
    StateCallback m_onStateChangedCallback;
    MessageCallback m_onConnectedCallback;
    MessageCallback m_onStatsCallback;
    MessageCallback m_onResultCallback;
    MessageCallback m_onPongCallback;
    ErrorCallback m_onErrorOccurredCallback;

    // 流式消息缓冲区
    QString m_streamBuffer;
};

#endif // WEBSOCKETCONTROLLER_H