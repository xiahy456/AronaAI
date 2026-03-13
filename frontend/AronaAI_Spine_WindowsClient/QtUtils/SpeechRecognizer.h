#pragma once
#ifndef SPEECHRECOGNIZER_H
#define SPEECHRECONIZER_H

#include "Defines.h"

#include <QObject>
#include <QString>
#include <QByteArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <QMutex>
#include <QWaitCondition>
#include "vosk_api.h"

// 语音识别结果结构体
struct RecognitionResult {
    QString text;           // 识别的文本
    QString partialText;    // 部分识别的文本
    double confidence;       // 置信度
    bool isFinal;            // 是否是最终结果
    QJsonObject fullJson;    // 完整的JSON结果

    RecognitionResult() : confidence(0.0), isFinal(false) {}
};

class SpeechRecognizer : public QObject
{
    Q_OBJECT

public:
    explicit SpeechRecognizer(QObject* parent = nullptr);
    ~SpeechRecognizer();

    // 初始化与配置
    bool initialize(const QString& modelPath, float sampleRate = 16000.0f);
    bool initializeWithSpeaker(const QString& modelPath, const QString& spkModelPath, float sampleRate = 16000.0f);
    bool initializeWithGrammar(const QString& modelPath, const QString& grammar, float sampleRate = 16000.0f);
    void shutdown();

    // 识别控制
    void startRecognition();
    void stopRecognition();
    void reset();
    bool isInitialized() const { return m_initialized; }
    bool isRecognizing() const { return m_recognizing; }

    // 配置选项
    void setMaxAlternatives(int maxAlternatives);
    void enableWords(bool enable);
    void enablePartialWords(bool enable);
    void enableNLSML(bool enable);
    void setGrammar(const QString& grammar);

    // 处理音频数据（主要接口）
    bool acceptWaveform(const QByteArray& audioData);
    bool acceptWaveform(const short* audioData, int length);

    // 获取结果
    RecognitionResult getResult();
    RecognitionResult getPartialResult();
    RecognitionResult getFinalResult();

    // 静态工具函数
    static QString version();
    static void setLogLevel(int level);
    static void initGPU();
    static void initGPUThread();

signals:
    void initialized();                          // 初始化完成
    void recognitionStarted();                    // 识别开始
    void recognitionStopped();                    // 识别停止
    void resultReady(const RecognitionResult& result);           // 最终结果就绪
    void partialResultReady(const RecognitionResult& result);    // 部分结果就绪
    void errorOccurred(const QString& error);     // 错误发生

private slots:
    void processPendingResults();                 // 处理待处理的结果

private:
    // Vosk 对象指针
    VoskModel* m_model;
    VoskSpkModel* m_spkModel;
    VoskRecognizer* m_recognizer;

    // 状态标志
    bool m_initialized;
    bool m_recognizing;
    float m_sampleRate;

    // 配置参数
    int m_maxAlternatives;
    bool m_wordsEnabled;
    bool m_partialWordsEnabled;
    bool m_nlsmlEnabled;
    QString m_grammar;

    // 线程同步
    QMutex m_mutex;
    QWaitCondition m_condition;

    // 临时存储
    RecognitionResult m_lastResult;
    RecognitionResult m_lastPartialResult;

    // 辅助函数
    RecognitionResult parseResult(const char* jsonResult);
    void clearResults();
    bool checkInitialized() const;
};

#endif // SPEECHRECOGNIZER_H