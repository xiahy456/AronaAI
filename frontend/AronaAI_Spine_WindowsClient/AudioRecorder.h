#pragma once

#include <QObject>

class AudioRecorder  : public QObject
{
	Q_OBJECT

public:
	AudioRecorder(QObject *parent);
	~AudioRecorder();
};

