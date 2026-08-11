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
#include <TencentSpeechRecognizer.h>
#include "WebSocketController.h"
#include "UserInputWidget.h"
#include "AronaEmotionMap.h"

class MainController : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, TencentSpeechRecognizer* speechRecognizer, WebSocketController* webSocketController, UserInputWidget* userInputWidget);
	~MainController();

	// 执行输出
	void executeOutput(const QString& text);
	// 开始录音、识别
	void startAudioProcessing();
	// 停止录音、识别
	void stopAudioProcessing();
	// 切换主界面鼠标穿透
	void toggleMouseTransparent();
	// 呼出用户文本输入界面
	void showUserInput();

private slots:
	// TTS工作完毕
	void onTTSFinished(const QByteArray& audioData, const QString& mediaType);
	// TTS失败（超时等）：仍显示字幕
	void onTTSError(const QString& errorString);
	// 音频输入出错
	void onAudioError(const QString& error);
	// 音频识别出错
	void onRecognizeError(const QString& error);
	// 处理识别结果
	void onRecognizeFinished(const QString& text);
	// WebSocket 相关槽函数
	void onWebSocketConnected(const QString& sessionId);
	void onWebSocketChatResponse(const QString& content, bool fromCache, const QString& contextUsed, double latency, const QString& emotion);
	void onWebSocketChatStream(const QString& content, bool done);
	void onWebSocketError(WebSocketController::ErrorCode code, const QString& message);
	void onWebSocketStateChanged(WebSocketController::ConnectionState state);

private:
	MainWidget* m_mainWidget;	// 主界面对象引用
	TTSManager* m_ttsManager;	// 语音合成管理器指针
	AudioRecorder* m_audioRecorder;	// 音频录制器对象
	TencentSpeechRecognizer* m_tencentRecognizer; // 腾讯的语音识别
	WebSocketController* m_webSocketController;	// 服务端websocket连接
	UserInputWidget* m_userInputWidget;	// 用户文本输入界面
	TTSManager::TTSRequestParams ttsRequestParams;	// 语音合成请求参数
	QString m_currentText = "";	// 当前正在处理的文本
	QString m_currentEmotion = "normal";	// 当前回复表情（英文值）
	bool m_waitingForAIResponse = false;	// 是否正在等待AI回复

	// 处理用户输入的文本（语音识别或文本输入）
	void processInputText(const QString& text);

};
