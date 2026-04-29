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

#include "Defines.h"
#include "GlobalVariables.h"

#include <QObject>
#include <QString>
#include <QEventLoop>
#include <QMessageBox>
#include <QProcess>

#include <MainWidget.h>
#include <TTSManager.h>
#include <AudioRecorder.h>
#include <SpeechRecognizer.h>
#include <TencentSpeechRecognizer.h>
#include "WebSocketController.h"

class MainController : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, TencentSpeechRecognizer* speechRecognizer, WebSocketController* webSocketController);
	~MainController();

	// 执行输出
	void executeOutput(const QString& text);
	// 开始录音、识别
	void startAudioProcessing();
	// 停止录音、识别
	void stopAudioProcessing();

private slots:
	// TTS工作完毕
	void onTTSFinished(const QByteArray& audioData, const QString& mediaType);
	// 音频输入出错
	void onAudioError(const QString& error);
	// 音频识别出错
	void onRecognizeError(const QString& error);
	// 处理识别结果
	void onRecognizeFinished(const QString& text);
	// WebSocket 相关槽函数
	void onWebSocketConnected(const QString& sessionId);
	void onWebSocketChatResponse(const QString& content, bool fromCache, bool contextUsed, double latency);
	void onWebSocketChatStream(const QString& content, bool done);
	void onWebSocketError(WebSocketController::ErrorCode code, const QString& message);
	void onWebSocketStateChanged(WebSocketController::ConnectionState state);

private:
	MainWidget* m_mainWidget;	// 主界面对象引用
	TTSManager* m_ttsManager;	// 语音合成管理器指针
	AudioRecorder* m_audioRecorder;	// 音频录制器对象
	//SpeechRecognizer* m_speechRecognizer;	// 语音识别器对象
	TencentSpeechRecognizer* m_tencentRecognizer; // 腾讯的语音识别
	WebSocketController* m_webSocketController;	// 服务端websocket连接
	TTSManager::TTSRequestParams ttsRequestParams;	// 语音合成请求参数
	QString m_currentText = "";	// 当前正在处理的文本
	bool m_waitingForAIResponse = false;	// 是否正在等待AI回复

	// 处理用户语音输入的文本
	void processInputText(const QString& text);

};
