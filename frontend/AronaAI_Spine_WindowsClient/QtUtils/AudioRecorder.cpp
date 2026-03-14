#include "AudioRecorder.h"

AudioRecorder::AudioRecorder(QObject* parent)
    : QObject(parent)
    , m_audioSource(nullptr)
    , m_audioBuffer(nullptr)
    , m_isRecording(false)
{
    // 配置音频格式
    m_format.setSampleRate(16000);      // 采样率 16kHz
    m_format.setChannelCount(1);         // 单声道
    m_format.setSampleFormat(QAudioFormat::Int16); // 16-bit 有符号整数 PCM

    // 检查设备支持情况
    QAudioDevice inputDevice = QMediaDevices::defaultAudioInput();
    if (!inputDevice.isFormatSupported(m_format)) {
        qWarning().noquote() << ERROR_PR << "[Audio Recorder]Default format not supported, trying to use nearest...";
        // Qt 6 中，QAudioDevice 也有 nearestFormat 方法
        m_format = inputDevice.preferredFormat();
    }
}

AudioRecorder::~AudioRecorder()
{
    stopRecording();
}

bool AudioRecorder::startRecording()
{
    if (m_isRecording) return false;

    m_audioData.clear();

    // 创建音频源
    QAudioDevice inputDevice = QMediaDevices::defaultAudioInput();
    if (inputDevice.isNull()) {
        emit errorOccurred("[Audio Recorder]Failed to find audio input device!");
        return false;
    }

    // 释放旧对象
    if (m_audioSource) {
        delete m_audioSource;
        m_audioSource = nullptr;
    }

    // 创建QAudioSource
    m_audioSource = new QAudioSource(inputDevice, m_format, this);

    // 创建内存缓冲区
    if (m_audioBuffer) {
        delete m_audioBuffer;
        m_audioBuffer = nullptr;
    }
    m_audioBuffer = new QBuffer(&m_audioData, this);

    if (!m_audioBuffer->open(QIODevice::WriteOnly)) {
        emit errorOccurred("[Audio Recorder]Failed to open audio buffer!");
        return false;
    }

    // 5. 开始录制 (Qt 6 的 start 方法接收 QIODevice*)
    m_audioSource->start(m_audioBuffer);
    m_isRecording = true;

    qDebug().noquote() << FINE_PR << "[Audio Recorder]Recording started";
    return true;
}

QByteArray AudioRecorder::stopRecording()
{
    if (!m_isRecording) return QByteArray();

    // 6. 停止录制
    if (m_audioSource) {
        m_audioSource->stop();
    }
    if (m_audioBuffer) {
        m_audioBuffer->close();
    }
    m_isRecording = false;

    qDebug().noquote() << FINE_PR << "[Audio Recorder]Recording stopped, captured" << m_audioData.size() << "bytes";
    return m_audioData;
}

bool AudioRecorder::isRecording() const
{
    return m_isRecording;
}
