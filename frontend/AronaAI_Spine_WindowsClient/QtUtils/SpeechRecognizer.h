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

#ifndef SPEECHRECOGNIZE_H
#define SPEECHRECOGNIZE_H

#include <Defines.h>

#include <QObject>
#include <QString>
#include <QDebug>
#include <vosk_api.h>

class SpeechRecognizer : public QObject
{
    Q_OBJECT

public:
    explicit SpeechRecognizer(QObject* parent = nullptr);
    ~SpeechRecognizer();

    // 初始化Vosk模型
    bool initialize(const QString& modelPath);

    // 识别音频数据
    QString recognize(const QByteArray& audioData);

    // 检查是否已初始化
    bool isInitialized() const;

signals:
    void errorOccurred(const QString& error);

private:
    VoskModel* m_model;
    VoskRecognizer* m_recognizer;
    bool m_initialized;
};

#endif // SPEECHRECOGNIZE_H