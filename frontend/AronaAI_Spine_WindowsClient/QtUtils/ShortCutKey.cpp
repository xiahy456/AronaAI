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

#include "ShortCutKey.h"

ShortCutKey::ShortCutKey(MainController* mainController)
	: m_mainController(mainController)
{
	// ³õÊ¼»¯ÈÈ¼ü
	// ÇÐ»»ÒôÆµÊäÈë
	m_switchAudioInput = new QHotkey(QKeySequence(GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input")), true, this);

	// ×¢²á¿ì½Ý¼ü
	// ÇÐ»»ÒôÆµÊäÈë
	if (m_switchAudioInput->isRegistered()) FINE_DEBUG_OUTPUT("[Short Cut Key]Key 'Switch Audio Input' registered succeed! Registered to: "
		+ GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input"));
	else ERROR_DEBUG_OUTPUT("[Short Cut Key]Key 'Switch Audio Input' registered failed! It might be occupied! Registered to:"
		+ GET_STRING_FROM_JSON(_global_config, "short_cut_key", "switch_audio_input"));

	// Á¬½ÓÐÅºÅ²Û
	// ÇÐ»»ÒôÆµÊäÈë
	connect(m_switchAudioInput, &QHotkey::activated, this, &ShortCutKey::onSwitchAudioInput);

}

ShortCutKey::~ShortCutKey()
{

}

void ShortCutKey::onSwitchAudioInput()
{
	FINE_DEBUG_OUTPUT("[Short Cut Key]Key 'Switch Audio Input' activated!");
	if (m_switchAudioInputEnabled) {
		m_mainController->stopAudioProcessing();
		m_switchAudioInputEnabled = false;
	}
	else {
		m_mainController->startAudioProcessing();
		m_switchAudioInputEnabled = true;
	}
}