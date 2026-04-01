#pragma once

#include <QObject>

class DebugManager  : public QObject
{
	Q_OBJECT

public:
    static DebugManager* instance();

    // 发送调试消息
    void sendDebugMessage(const QString& message, const QString& sender = "");

signals:
    // 调试消息信号
    void debugMessageReceived(const QString& message);

private:
    explicit DebugManager(QObject* parent = nullptr);
    static DebugManager* m_instance;
};

