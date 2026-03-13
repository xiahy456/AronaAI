#pragma once

#include <QObject>

class SpeechRecognizer  : public QObject
{
	Q_OBJECT

public:
	SpeechRecognizer(QObject *parent);
	~SpeechRecognizer();
};

