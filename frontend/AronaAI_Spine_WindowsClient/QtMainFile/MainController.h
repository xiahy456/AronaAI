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

class MainController : public QObject
{
	Q_OBJECT

public:
	MainController(MainWidget* mainWidget, TTSManager* ttsManager, AudioRecorder* audioRecorder, TencentSpeechRecognizer* speechRecognizer);
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

private:
	MainWidget* m_mainWidget;	// 主界面对象引用
	TTSManager* m_ttsManager;	// 语音合成管理器指针
	AudioRecorder* m_audioRecorder;	// 音频录制器对象
	//SpeechRecognizer* m_speechRecognizer;	// 语音识别器对象
	TencentSpeechRecognizer* m_tencentRecognizer; // 腾讯的语音识别
	TTSManager::TTSRequestParams ttsRequestParams;	// 语音合成请求参数
	QString m_currentText = "";	// 当前正在处理的文本

	// 处理用户语音输入的文本
	void processInputText(const QString& text);

};
