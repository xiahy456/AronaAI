#pragma once

#include "Defines.h"
#include "GlobalVariables.h"

#include <QObject>
#include <QString>
#include <QEventLoop>

#include <MainWidget.h>
#include <TTSManager.h>
#include <AudioRecorder.h>
#include <SpeechRecognizer.h>

class MainController : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, SpeechRecognizer* speechRecognizer);
	~MainController();

	// 执行输出
	void executeOutput(const QString& text);
	// 开始录音、识别
	bool startAudioProcessing();
	// 停止录音、识别
	void stopAudioProcessing();
	// 处理音频文件（离线识别）
	bool processAudioFile(const QString& filePath);
	// 获取识别结果（同步方式）
	QString recognizeSync(int durationMs = 5000);

signals:
	void resultAvailable(const QString& text);
	void partialResultAvailable(const QString& text);

private slots:
	void onTTSFinished(const QByteArray& audioData, const QString& mediaType);
	void onRecordingStarted();
	void onRecordingStopped();
	void onAudioDataReady(const QByteArray& data);
	void onResultReady(const RecognitionResult& result);
	void onPartialResultReady(const RecognitionResult& result);
	void onError(const QString& error);
	void onAudioLevelChanged(int level);

private:
	MainWidget* m_mainWidget;	// 主界面对象引用
	TTSManager* m_ttsManager;	// 语音合成管理器指针
	AudioRecorder* m_audioRecorder;	// 音频录制器对象
	SpeechRecognizer* m_speechRecognizer;	// 语音识别器对象
	TTSManager::TTSRequestParams ttsRequestParams;	// 语音合成请求参数
	QString m_currentText = "";	// 当前正在处理的文本
	bool m_isRecording = false;	// 是否正在录音

	// 初始化Vosk语音识别引擎
	bool initializeVosk();

};
