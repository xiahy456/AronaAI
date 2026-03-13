#ifndef AUDIORECORDER_H
#define AUDIORECORDER_H

#include <QObject>
#include <QAudioSource>
#include <QBuffer>
#include <QByteArray>
#include <QTimer>
#include <QElapsedTimer>
#include <QMediaDevices>
#include <QAudioDevice>

#include "Defines.h"

class AudioRecorder : public QObject
{
    Q_OBJECT

public:
    explicit AudioRecorder(QObject* parent = nullptr);
    ~AudioRecorder();

    // 公共接口
    bool startRecording();              // 开始录音
    void stopRecording();                // 停止录音
    bool isRecording() const;            // 是否正在录音
    void setStreamMode(bool enable);     // 设置为流式模式
    void setStreamInterval(int ms);      // 设置流式模式的数据推送间隔

    // 获取音频数据
    QByteArray getRecordedData() const;  // 获取录制的完整音频数据
    void clearRecordedData();            // 清除已录制的数据

signals:
    void recordingStarted();             // 录音开始信号
    void recordingStopped();             // 录音停止信号
    void recordingError(const QString& error);  // 错误信号
    void audioDataReady(const QByteArray& data); // 新音频数据就绪信号
    void audioLevelChanged(int level);   // 音频电平变化信号

private slots:
    void processAudioData();             // 处理音频数据（用于流式模式）
    void updateAudioLevel();              // 更新音频电平

private:
    void setupAudioFormat();              // 设置音频格式
    bool initializeAudioSource();         // 初始化音频源

private:
    QAudioSource* m_audioSource = nullptr;
    QAudioFormat m_audioFormat;
    QBuffer* m_audioBuffer = nullptr;
    QByteArray m_recordedData;

    bool m_isRecording = false;
    bool m_streamMode = false;
    int m_streamInterval = 200;

    QTimer* m_streamTimer = nullptr;
    QTimer* m_levelTimer = nullptr;
    QElapsedTimer m_recordingTimer;

    static constexpr int SAMPLE_RATE = 16000;
    static constexpr int CHANNEL_COUNT = 1;
    static constexpr int SAMPLE_SIZE = 16;
    static constexpr int AUDIO_LEVEL_INTERVAL = 50;
};

#endif // AUDIORECORDER_H