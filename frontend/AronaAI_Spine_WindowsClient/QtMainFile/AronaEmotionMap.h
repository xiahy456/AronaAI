/*
 Copyright xia_hy456. All rights reserved.

 Emotion English value -> Spine expression-layer animation id.
 Keep in sync with Assets/AronaSpineAssets/README.md
*/

#pragma once

#include <QHash>
#include <QString>

namespace AronaEmotion {

inline const QHash<QString, QString>& englishToAnim()
{
    static const QHash<QString, QString> kMap = {
        {QStringLiteral("normal"), QStringLiteral("00")},
        {QStringLiteral("curious"), QStringLiteral("02")},
        {QStringLiteral("smile"), QStringLiteral("03")},
        {QStringLiteral("worried"), QStringLiteral("04")},
        {QStringLiteral("angry"), QStringLiteral("05")},
        {QStringLiteral("angry_shame"), QStringLiteral("06")},
        {QStringLiteral("disgusted"), QStringLiteral("07")},
        {QStringLiteral("disgusted_surprised"), QStringLiteral("08")},
        {QStringLiteral("disgusted_worried"), QStringLiteral("09")},
        {QStringLiteral("frustration"), QStringLiteral("10")},
        {QStringLiteral("like"), QStringLiteral("11")},
        {QStringLiteral("very_happy"), QStringLiteral("12")},
        {QStringLiteral("enjoy"), QStringLiteral("13")},
        {QStringLiteral("complaint"), QStringLiteral("14")},
        {QStringLiteral("unwilling"), QStringLiteral("15")},
        {QStringLiteral("shy"), QStringLiteral("16")},
        {QStringLiteral("shout"), QStringLiteral("20")},
        {QStringLiteral("want"), QStringLiteral("21")},
        {QStringLiteral("confident_serious"), QStringLiteral("22")},
        {QStringLiteral("sleep_very_content"), QStringLiteral("23")},
        {QStringLiteral("sleep_question"), QStringLiteral("24")},
        {QStringLiteral("confident"), QStringLiteral("25")},
        {QStringLiteral("disappointed"), QStringLiteral("26")},
        {QStringLiteral("disappointed_disgusted"), QStringLiteral("27")},
        {QStringLiteral("very_surprised"), QStringLiteral("28")},
        {QStringLiteral("dizzy"), QStringLiteral("29")},
        {QStringLiteral("surprise"), QStringLiteral("31")},
        {QStringLiteral("surprise_very_happy"), QStringLiteral("32")},
        {QStringLiteral("sleep"), QStringLiteral("99")},
    };
    return kMap;
}

/** Map backend emotion English value to Spine track-1 animation name. */
inline QString toAnimationName(const QString& emotionEnglish)
{
    const QString key = emotionEnglish.trimmed().toLower();
    const auto& map = englishToAnim();
    return map.value(key, QStringLiteral("00"));
}

}  // namespace AronaEmotion
