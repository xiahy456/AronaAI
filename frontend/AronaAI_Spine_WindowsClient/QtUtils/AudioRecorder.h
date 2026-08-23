/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain the License at
    https://www.apache.org/licenses/LICENSE-2.0
*/

#pragma once
#ifndef AUDIORECORDER_H
#define AUDIORECORDER_H

#include "Defines.h"

#include <QObject>
#include <QAudioSource>
#include <QMediaDevices>
#include <QAudioDevice>
#include <QAudioFormat>
#include <QIODevice>
#include <QByteArray>

class AudioRecorder : public QObject
{
    Q_OBJECT

public:
    explicit AudioRecorder(QObject* parent = nullptr);
    ~AudioRecorder();

    bool startRecording();
    void stopRecording();
    bool isRecording() const;
    void setPlaybackGuard(bool enabled);

signals:
    void errorOccurred(const QString& error);
    void pcmFrameReady(const QByteArray& frame);
    void speechDetected();

private:
    class CaptureDevice;

    void onPcmWritten(const QByteArray& data);
    bool looksLikeSpeech(const QByteArray& data, int* durationMs) const;

    QAudioSource* m_audioSource;
    CaptureDevice* m_captureDevice;
    QAudioFormat m_format;
    bool m_isRecording;
    bool m_playbackGuard;
    int m_speechMs;
    bool m_speechLatched;
};

#endif // AUDIORECORDER_H
