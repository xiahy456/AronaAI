#pragma once

#include <QObject>
#include <QDateTime>
#include <QTime>

class DebugManager  : public QObject
{
	Q_OBJECT

public:
    static DebugManager* instance();

    // 发送调试消息
    void sendDebugMessage(const QString& message, const QString& sender = "");

    // 获取缓存的调试信息
    void flushPendingMessages();

signals:
    // 调试消息信号
    void debugMessageReceived(const QString& message);

private:
    explicit DebugManager(QObject* parent = nullptr);
    static DebugManager* m_instance;
    QStringList m_pendingMessages;  // 缓存未发送的消息
};

