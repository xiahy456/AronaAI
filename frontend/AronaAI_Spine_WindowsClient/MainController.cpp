#include "MainController.h"

MainController::MainController(MainWidget& mainWidget, TTSManager& ttsManager) :
	m_mainWidget(mainWidget),
	m_ttsManager(ttsManager)
{
	// 进行TTS初始化
	// 为TTS设置GPT模型
	//m_ttsManager.setGPTWeights(GET_STRING_FROM_JSON(_global_config, "tts", "gpt_path"));
	// GPT设置完毕后，为TTS设置SoVITS模型

}

MainController::~MainController()
{

}

void MainController::executeOutput(const QString& text)
{
	// 当TTS没有与GPT-SoVITS交互时，将文本送至TTS模块进行语音合成

	// 语音合成完毕后，将语音数据发送至音频输出模块进行播放

	// 同时调用MainWidget文本显示在界面上
	m_mainWidget.showOutputText(text);
}

