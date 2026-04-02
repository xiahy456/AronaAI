#include "DebugManager.h"

DebugManager* DebugManager::m_instance = nullptr;

DebugManager* DebugManager::instance()
{
    if (!m_instance) {
        m_instance = new DebugManager();
    }
    return m_instance;
}

DebugManager::DebugManager(QObject* parent) : QObject(parent)
{
}

void DebugManager::sendDebugMessage(const QString& message, const QString& sender)
{
    QString formattedMsg;
    if (!sender.isEmpty()) {
        formattedMsg = QString("[%1][%2]%3").arg(sender).arg(QTime::currentTime().toString("hh:mm:ss")).arg(message);
    }
    else {
        formattedMsg = message;
    }

    //emit debugMessageReceived(formattedMsg);
    // 检查是否有接收者
    if (receivers(SIGNAL(debugMessageReceived(QString))) > 0) {
        emit debugMessageReceived(formattedMsg);
    }
    else {
        m_pendingMessages.append(formattedMsg);  // 缓存
    }
}

void DebugManager::flushPendingMessages()
{
    for (const QString& msg : m_pendingMessages) {
        emit debugMessageReceived(msg);
    }
    m_pendingMessages.clear();
}
