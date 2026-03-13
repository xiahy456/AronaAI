#include "ShortCutKey.h"

ShortCutKey::ShortCutKey(MainController* mainController)
	: m_mainController(mainController)
{
	// ³õÊ¼»¯ÈÈ¼ü
	// ÇÐ»»ÒôÆµÊäÈë
	m_switchAudioInput = new QHotkey(QKeySequence(GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input")), true, this);

	// ×¢²á¿ì½Ý¼ü
	// ÇÐ»»ÒôÆµÊäÈë
	if (m_switchAudioInput->isRegistered()) qDebug().noquote() << FINE_PR << "[Short Cut Key]Key 'Switch Audio Input' registered succeed! Registered to: "
		<< GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input");
	else qWarning() << ERROR_PR << "[Short Cut Key]Key 'Switch Audio Input' registered failed! It might be occupied! Registered to:"
		<< GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input");

	// Á¬½ÓÐÅºÅ²Û
	// ÇÐ»»ÒôÆµÊäÈë
	connect(m_switchAudioInput, &QHotkey::activated, this, &ShortCutKey::onSwitchAudioInput);

}

ShortCutKey::~ShortCutKey()
{

}

void ShortCutKey::onSwitchAudioInput()
{
	qDebug().noquote() << FINE_PR << "[Short Cut Key]Key 'Switch Audio Input' activated!";
	if (m_switchAudioInputEnabled) {
		m_mainController->stopAudioProcessing();
		m_switchAudioInputEnabled = false;
	}
	else {
		m_mainController->startAudioProcessing();
		m_switchAudioInputEnabled = true;
	}
}