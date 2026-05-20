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

class AudioWorker;
class QThread;

class MainController : public QObject
{
	Q_OBJECT

public:
	enum AudioState {
		Idle,               // No recording or processing
		WakeWordListening,  // Continuous mode active, waiting for wake word
		RecordingUtterance, // Recording user speech after wake word detected
		ProcessingASR,      // Sending audio to ASR, waiting for result
		WaitingForAI,       // AI response in progress
		PlayingTTS          // TTS audio playing
	};

	MainController(MainWidget* mainWidget, TTSManager* ttsManager,
	               AudioRecorder* audioRecorder, TencentSpeechRecognizer* speechRecognizer,
	               WebSocketController* webSocketController,
	               AudioWorker* audioWorker, QThread* workerThread);
	~MainController();

	void executeOutput(const QString& text);
	void startAudioProcessing();
	void stopAudioProcessing();

	bool enableWakeWord(const QString& modelDir, const QString& keywordsFile);
	void disableWakeWord();
	AudioState currentState() const { return m_audioState; }

private slots:
	void onTTSFinished(const QByteArray& audioData, const QString& mediaType);
	void onAudioError(const QString& error);
	void onRecognizeError(const QString& error);
	void onRecognizeFinished(const QString& text);
	void onWebSocketConnected(const QString& sessionId);
	void onWebSocketChatResponse(const QString& content, bool fromCache, bool contextUsed, double latency);
	void onWebSocketChatStream(const QString& content, bool done);
	void onWebSocketError(WebSocketController::ErrorCode code, const QString& message);
	void onWebSocketStateChanged(WebSocketController::ConnectionState state);
	void onWakeWordDetected(const QString& keyword);
	void onWakeWordError(const QString& error);
	void onUtteranceComplete(const QByteArray& audioData);

private:
	MainWidget* m_mainWidget;
	TTSManager* m_ttsManager;
	AudioRecorder* m_audioRecorder;
	TencentSpeechRecognizer* m_tencentRecognizer;
	WebSocketController* m_webSocketController;
	AudioWorker* m_audioWorker;
	QThread* m_workerThread;
	TTSManager::TTSRequestParams ttsRequestParams;
	QString m_currentText = "";
	bool m_waitingForAIResponse = false;
	AudioState m_audioState = AudioState::Idle;

	void processInputText(const QString& text);
};
