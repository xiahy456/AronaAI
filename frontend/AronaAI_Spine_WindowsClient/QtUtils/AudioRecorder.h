/*
 Copyright xia_hy456. All rights reserved.

 @Author: xia_hy456
 @Date: 2026/3/14 22:15:53

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

#pragma once
#ifndef AUDIORECORDER_H
#define AUDIORECORDER_H

#include "Defines.h"

#include <QObject>
#include <QAudioSource> // Qt 6: ʹ�� QAudioSource
#include <QMediaDevices> // Qt 6: ���ڻ�ȡ�豸��Ϣ
#include <QAudioDevice>
#include <QAudioFormat>
#include <QBuffer>
#include <QByteArray>
#include <QDebug>
#include <QTimer>

// Number of 16-bit samples per chunk (512 = 32ms @ 16kHz, matches Sherpa-onnx frame)
#define AUDIO_CHUNK_SAMPLES 512

class AudioRecorder : public QObject
{
    Q_OBJECT

public:
    explicit AudioRecorder(QObject* parent = nullptr);
    ~AudioRecorder();

    // On-demand recording (existing, unchanged)
    bool startRecording();
    QByteArray stopRecording();
    bool isRecording() const;

    // Continuous streaming for wake-word detection
    bool startContinuous();
    void stopContinuous();
    bool isContinuousActive() const;

signals:
    void errorOccurred(const QString& error);
    void audioChunkReady(const QByteArray& chunk);  // int16 PCM, AUDIO_CHUNK_SAMPLES frames

private:
    QAudioSource* m_audioSource = nullptr;
    QBuffer* m_audioBuffer = nullptr;
    QByteArray m_audioData;
    QAudioFormat m_format;
    bool m_isRecording = false;

    // Continuous mode
    QTimer* m_continuousTimer = nullptr;
    qint64 m_chunkOffset = 0;
};

#endif // AUDIORECORDER_H