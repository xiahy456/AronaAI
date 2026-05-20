#include "WakeWordDetector.h"
#include "Defines.h"
#include "sherpa-onnx/c-api/c-api.h"

#include <QString>
#include <QDebug>

WakeWordDetector::WakeWordDetector(QObject* parent)
    : QObject(parent)
{
}

WakeWordDetector::~WakeWordDetector()
{
    if (m_stream) {
        SherpaOnnxDestroyOnlineStream(m_stream);
        m_stream = nullptr;
    }
    if (m_kws) {
        SherpaOnnxDestroyKeywordSpotter(m_kws);
        m_kws = nullptr;
    }
}

bool WakeWordDetector::initialize(const QString& modelDir, const QString& keywordsFile)
{
    if (m_initialized) return true;

    QByteArray encoderPath = (modelDir + "/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx").toUtf8();
    QByteArray decoderPath = (modelDir + "/decoder-epoch-12-avg-2-chunk-16-left-64.onnx").toUtf8();
    QByteArray joinerPath  = (modelDir + "/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx").toUtf8();
    QByteArray tokensPath  = (modelDir + "/tokens.txt").toUtf8();
    QByteArray kwPath      = keywordsFile.toUtf8();

    SherpaOnnxKeywordSpotterConfig config;
    memset(&config, 0, sizeof(config));

    config.model_config.transducer.encoder = encoderPath.constData();
    config.model_config.transducer.decoder = decoderPath.constData();
    config.model_config.transducer.joiner  = joinerPath.constData();
    config.model_config.tokens   = tokensPath.constData();
    config.model_config.provider  = "cpu";
    config.model_config.num_threads = 1;
    config.keywords_file = kwPath.constData();

    m_kws = SherpaOnnxCreateKeywordSpotter(&config);
    if (!m_kws) {
        FINE_DEBUG_OUTPUT("[WakeWord] Failed to create keyword spotter — falling back to hotkey-only mode");
        emit errorOccurred("Wake word unavailable, falling back to hotkey mode");
        m_degraded = true;
        return false;
    }

    m_stream = SherpaOnnxCreateKeywordStream(m_kws);
    if (!m_stream) {
        SherpaOnnxDestroyKeywordSpotter(m_kws);
        m_kws = nullptr;
        FINE_DEBUG_OUTPUT("[WakeWord] Failed to create keyword stream");
        emit errorOccurred("Wake word unavailable, falling back to hotkey mode");
        m_degraded = true;
        return false;
    }

    m_initialized = true;
    FINE_DEBUG_OUTPUT("[WakeWord] Initialized successfully");
    return true;
}

void WakeWordDetector::processFrame(const QVector<float>& samples)
{
    if (!m_kws || !m_stream) return;

    SherpaOnnxOnlineStreamAcceptWaveform(
        m_stream, 16000, samples.constData(), samples.size());

    while (SherpaOnnxIsKeywordStreamReady(m_kws, m_stream)) {
        SherpaOnnxDecodeKeywordStream(m_kws, m_stream);
        const SherpaOnnxKeywordResult* r =
            SherpaOnnxGetKeywordResult(m_kws, m_stream);

        if (r && r->keyword && strlen(r->keyword) > 0) {
            emit wakeWordDetected(QString::fromUtf8(r->keyword));
            SherpaOnnxResetKeywordStream(m_kws, m_stream);
        }
        SherpaOnnxDestroyKeywordResult(r);
    }
}
