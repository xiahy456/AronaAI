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