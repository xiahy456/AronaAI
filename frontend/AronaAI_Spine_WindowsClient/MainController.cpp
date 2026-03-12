#include "MainController.h"

MainController::MainController(MainWidget& mainWidget, TTSManager* ttsManager) :
	m_mainWidget(mainWidget),
	m_ttsManager(ttsManager)
{
	// 进行TTS初始化
	// 构建TTS请求参数
    ttsRequestParams.text = "";  // 要合成的文本
    ttsRequestParams.textLang = GET_STRING_FROM_JSON(_global_config, "tts", "text_lang");    // 文本语言
    ttsRequestParams.refAudioPath = GET_STRING_FROM_JSON(_global_config, "tts", "ref_audio_path");  // 参考音频路径
    ttsRequestParams.auxRefAudioPaths;   // 辅助参考音频路径
    ttsRequestParams.promptText = GET_STRING_FROM_JSON(_global_config, "tts", "prompt_text");    // 提示文本
    ttsRequestParams.promptLang = "zh";  // 提示文本语言
    ttsRequestParams.topK = 5;   // top k采样
    ttsRequestParams.topP = 1.0;  // top p采样
    ttsRequestParams.temperature = 1.0;   // 温度参数
    ttsRequestParams.textSplitMethod = "cut0";   // 文本分割方法
    ttsRequestParams.batchSize = 1;  // 批处理大小
    ttsRequestParams.batchThreshold = 0.75;   // 批处理阈值
    ttsRequestParams.splitBucket = true;    // 是否分割桶
    ttsRequestParams.speedFactor = 1.0;   // 语速因子
    ttsRequestParams.fragmentInterval = 0.3;  // 片段间隔
    ttsRequestParams.seed = -1;  // 随机种子
    ttsRequestParams.streamingMode = false; // 流式模式
    ttsRequestParams.parallelInfer = true;  // 并行推理
    ttsRequestParams.repetitionPenalty = 1.35;    // 重复惩罚
    ttsRequestParams.sampleSteps = 32;   // 采样步数
    ttsRequestParams.superSampling = false; // 超采样
    ttsRequestParams.mediaType = "wav";  // 媒体类型

    int m_modelsLoaded = 0; // 已加载的模型计数器
    const int TOTAL_MODELS = 2;  // 总共需要加载的模型数

	// 为TTS设置GPT模型
	m_ttsManager->setGPTWeights(GET_STRING_FROM_JSON(_global_config, "tts", "gpt_path"));
    
	// 为TTS设置SoVITS模型
    m_ttsManager->setSovitsWeights(GET_STRING_FROM_JSON(_global_config, "tts", "sovits_path"));

    // 连接信号，使用计数器判断两个模型都加载完成
	QEventLoop loop; // 创建事件循环
    connect(m_ttsManager, &TTSManager::modelSwitched, this,
        [&](bool success, const QString& message) {
            m_modelsLoaded++;
            qDebug().noquote() << FINE_PR << "[GPT-SoVITs]Model set：" << success
                << ", Message: " << message
                << "(" << m_modelsLoaded << "/" << TOTAL_MODELS << ")";

            // 当两个模型都加载完成时退出事件循环
            if (m_modelsLoaded >= TOTAL_MODELS) {
                loop.quit();
            }
        });
    // 启动事件循环，等待模型设置完成
    if (m_modelsLoaded < TOTAL_MODELS) {
        loop.exec();
    }
	qDebug().noquote() << FINE_PR << "[GPT-SoVITs]All models loaded";
    
    // 设置信号与槽
	connect(m_ttsManager, &TTSManager::ttsFinished, this, &MainController::onTTSFinished);

	// 测试：输出一段文本，验证TTS功能是否正常
    executeOutput("已连接至系统管理员阿罗娜。欢迎回来，老师。");
}

MainController::~MainController()
{

}

void MainController::executeOutput(const QString& text)
{
	// 将文本添加进TTS请求参数中
    ttsRequestParams.text = text;
    // 保存该文本
    m_currentText = text;
    // 调用TTSManager进行文本到语音的转换
	m_ttsManager->requestTTSPost(ttsRequestParams);

}

void MainController::onTTSFinished(const QByteArray& audioData, const QString& mediaType)
{
    // 播放音频
    m_ttsManager->playAudio(audioData);
    // 调试：保存音频
	//m_ttsManager->saveAudioToFile(audioData, "D:/Code/projects/Arona/output.wav");
    // 显示文字
    m_mainWidget.showOutputText(m_currentText);
    // 计算播放时长
	int duration = m_currentText.size() * 100; // 简单估算：每个字符100ms
	duration = (int)(1000 * (m_ttsManager->getWavDuration(audioData)));   // 按照实际音频时长设置，单位为毫秒
    // 启动动画
    m_mainWidget.setAnimation("Arona_Work_In_1_CN", 2, true);
	// 在duration之后清除显示的文字，停止动画
    QTimer::singleShot(duration, this, [this]() {
        m_mainWidget.hideOutputText();
        m_mainWidget.setAnimation("00", 2, true);
		});
}