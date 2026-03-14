#pragma once
#ifndef AUDIORECORDER_H
#define AUDIORECORDER_H

#include "Defines.h"

#include <QObject>
#include <QAudioSource> // Qt 6: 使用 QAudioSource
#include <QMediaDevices> // Qt 6: 用于获取设备信息
#include <QAudioDevice>
#include <QAudioFormat>
#include <QBuffer>
#include <QByteArray>
#include <QDebug>

class AudioRecorder : public QObject
{
    Q_OBJECT

public:
    explicit AudioRecorder(QObject* parent = nullptr);
    ~AudioRecorder();

    bool startRecording();
    QByteArray stopRecording();
    bool isRecording() const;

signals:
    void errorOccurred(const QString& error);

private:
    QAudioSource* m_audioSource;
    QBuffer* m_audioBuffer;
    QByteArray m_audioData;
    QAudioFormat m_format;
    bool m_isRecording;
};

#endif // AUDIORECORDER_H