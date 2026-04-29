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
    m_format.setSampleFormat(QAudioFormat::Int16); // 16-bit

    // 检查设备支持情况
    QAudioDevice inputDevice = QMediaDevices::defaultAudioInput();
    if (!inputDevice.isFormatSupported(m_format)) {
        ERROR_DEBUG_OUTPUT("[Audio Recorder]Default format not supported, trying to use nearest...");
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

    FINE_DEBUG_OUTPUT("[Audio Recorder]Recording started");
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

    FINE_DEBUG_OUTPUT("[Audio Recorder]Recording stopped, captured" + QString::number(m_audioData.size())+ "bytes");
    return m_audioData;
}

bool AudioRecorder::isRecording() const
{
    return m_isRecording;
}
