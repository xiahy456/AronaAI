/*
 Copyright xia_hy456. All rights reserved.

 Split spoken reply text into subtitle/TTS segments of at most 40 chars.
 Prefer complete sentences; only then binary-split overlong sentences
 at clause punctuation.
*/

#pragma once

#include <QString>
#include <QStringList>

namespace SpokenTextSplitter {

constexpr int kMaxSpokenSegmentChars = 40;

QStringList split(const QString& text);

} // namespace SpokenTextSplitter
