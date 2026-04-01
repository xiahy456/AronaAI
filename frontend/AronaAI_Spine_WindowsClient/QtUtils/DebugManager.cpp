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
        formattedMsg = QString("[%1] %2").arg(sender).arg(message);
    }
    else {
        formattedMsg = message;
    }

    emit debugMessageReceived(formattedMsg);
}