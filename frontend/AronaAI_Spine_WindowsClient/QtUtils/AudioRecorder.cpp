#include "AudioRecorder.h"
#include <QDebug>
#include <QAudio>

AudioRecorder::AudioRecorder(QObject* parent)
    : QObject(parent)
{
    setupAudioFormat();
    m_streamTimer = new QTimer(this);
    m_streamTimer->setInterval(m_streamInterval);
    connect(m_streamTimer, &QTimer::timeout, this, &AudioRecorder::processAudioData);

    m_levelTimer = new QTimer(this);
    m_levelTimer->setInterval(AUDIO_LEVEL_INTERVAL);
    connect(m_levelTimer, &QTimer::timeout, this, &AudioRecorder::updateAudioLevel);
}

AudioRecorder::~AudioRecorder()
{
    if (m_audioSource) {
        m_audioSource->stop();
        delete m_audioSource;
    }

    if (m_audioBuffer) {
        m_audioBuffer->close();
        delete m_audioBuffer;
    }
}

void AudioRecorder::setupAudioFormat()
{
    m_audioFormat.setSampleRate(SAMPLE_RATE);
    m_audioFormat.setChannelCount(CHANNEL_COUNT);
    m_audioFormat.setSampleFormat(QAudioFormat::Int16);
}

bool AudioRecorder::initializeAudioSource()
{
    QAudioDevice inputDevice = QMediaDevices::defaultAudioInput();
    if (inputDevice.isNull()) {
        emit recordingError("[Audio Record]Failed to find available microphone!");  // 发送错误信号
        return false;
    }

    if (!inputDevice.isFormatSupported(m_audioFormat)) {
        qWarning() << ERROR_PR << "[Audio Record]Default format is not supported, please choose other formats!";
        m_audioFormat = inputDevice.preferredFormat();

        if (m_audioFormat.sampleRate() != SAMPLE_RATE ||
            m_audioFormat.channelCount() != CHANNEL_COUNT ||
            m_audioFormat.sampleFormat() != QAudioFormat::Int16) {

            QString errorMsg = QString("[Audio Record]Failed to set correct audio format! Current format: %1Hz | %2 channel | %3")
                .arg(m_audioFormat.sampleRate())
                .arg(m_audioFormat.channelCount())
                .arg(m_audioFormat.sampleFormat() == QAudioFormat::Int16 ? "Int16" : "Other format");

            emit recordingError(errorMsg);  // 发送错误信号
            return false;
        }
    }

    if (m_audioSource) {
        delete m_audioSource;
    }
    m_audioSource = new QAudioSource(inputDevice, m_audioFormat, this);

    connect(m_audioSource, &QAudioSource::stateChanged,
        this, [this](QAudio::State newState) {
            switch (newState) {
            case QAudio::ActiveState:
                qDebug().noquote() << FINE_PR << "[Audio Record]Audio source ativated!";
                break;
            case QAudio::SuspendedState:
                qDebug().noquote() << FINE_PR << "[Audio Record]Audio source suspend!";
                break;
            case QAudio::StoppedState:
                qDebug().noquote() << FINE_PR << "[Audio Record]Audio source stopped!";
                if (m_audioSource && m_audioSource->error() != QAudio::NoError) {
                    emit recordingError("[Audio Record]Audio device error: " + QString::number(m_audioSource->error()));
                }
                break;
            case QAudio::IdleState:
                qDebug().noquote() << FINE_PR << "[Audio Record]Audio Source is free!";
                break;
            default:
                break;
            }
        });

    return true;
}

bool AudioRecorder::startRecording()
{
    if (m_isRecording) {
        qWarning() << ERROR_PR << "[Audio Record]It is recording!";
        return false;
    }

    if (!initializeAudioSource()) {
        return false;
    }

    if (m_audioBuffer) {
        m_audioBuffer->close();
        delete m_audioBuffer;
    }

    m_audioBuffer = new QBuffer(this);
    if (!m_audioBuffer->open(QIODevice::WriteOnly | QIODevice::ReadWrite)) {
        emit recordingError("[Audio Record]Failed to create audio buffer!");
        return false;
    }

    m_recordedData.clear();

    QIODevice* ioDevice = m_audioSource->start();
    if (!ioDevice) {
        emit recordingError("[Audio Record]Failed to start audio source!");
        return false;
    }

    connect(ioDevice, &QIODevice::readyRead, this, [this, ioDevice]() {
        QByteArray data = ioDevice->readAll();
        if (!data.isEmpty()) {
            m_audioBuffer->write(data);
            if (m_streamMode) {
                emit audioDataReady(data);  // 发送音频数据信号
            }
        }
        });

    m_isRecording = true;

    if (m_streamMode) {
        m_streamTimer->start();
    }
    m_levelTimer->start();

    m_recordingTimer.start();
    emit recordingStarted();  // 发送开始信号

    qDebug() << FINE_PR << "[Audio Record]Start recording! Audio format: "
        << m_audioFormat.sampleRate() << "Hz | "
        << m_audioFormat.channelCount() << "channel | "
        << m_audioFormat.sampleFormat();

    return true;
}

void AudioRecorder::stopRecording()
{
    if (!m_isRecording || !m_audioSource) {
        return;
    }

    m_audioSource->stop();
    m_audioSource->disconnect(this);

    m_streamTimer->stop();
    m_levelTimer->stop();

    if (m_audioBuffer) {
        m_audioBuffer->seek(0);
        m_recordedData = m_audioBuffer->readAll();
        m_audioBuffer->close();
        delete m_audioBuffer;
        m_audioBuffer = nullptr;
    }

    m_isRecording = false;

    qint64 duration = m_recordingTimer.elapsed();
    qDebug() << FINE_PR << "[Audio Record]Record stopped! Duration: " << duration << "ms | Data size："
        << m_recordedData.size() << "bytes";

    emit recordingStopped();  // 发送停止信号

    if (!m_streamMode && !m_recordedData.isEmpty()) {
        emit audioDataReady(m_recordedData);  // 发送完整音频数据信号
    }

    delete m_audioSource;
    m_audioSource = nullptr;
}

void AudioRecorder::processAudioData()
{
    // 流式模式已经在 readyRead 中实时处理
    // 这个函数保留供扩展使用
}

void AudioRecorder::updateAudioLevel()
{
    if (!m_isRecording || !m_audioBuffer || m_audioBuffer->size() == 0) {
        emit audioLevelChanged(0);  // 没有声音时发送0
        return;
    }

    m_audioBuffer->seek(m_audioBuffer->size() - qMin(4096, (int)m_audioBuffer->size()));
    QByteArray recentData = m_audioBuffer->readAll();

    if (recentData.size() >= 2) {
        int maxAmp = 0;
        const qint16* samples = reinterpret_cast<const qint16*>(recentData.constData());
        int sampleCount = recentData.size() / 2;

        for (int i = 0; i < qMin(1000, sampleCount); ++i) {
            int amp = qAbs(samples[i]);
            if (amp > maxAmp) {
                maxAmp = amp;
            }
        }

        int level = qMin(100, maxAmp * 100 / 32768);
        emit audioLevelChanged(level);  // 发送电平信号
    }
    else {
        emit audioLevelChanged(0);
    }
}

bool AudioRecorder::isRecording() const
{
    return m_isRecording;
}

void AudioRecorder::setStreamMode(bool enable)
{
    m_streamMode = enable;
}

void AudioRecorder::setStreamInterval(int ms)
{
    m_streamInterval = ms;
    if (m_streamTimer) {
        m_streamTimer->setInterval(ms);
    }
}

QByteArray AudioRecorder::getRecordedData() const
{
    return m_recordedData;
}

void AudioRecorder::clearRecordedData()
{
    m_recordedData.clear();
    if (m_audioBuffer) {
        m_audioBuffer->buffer().clear();
    }
}