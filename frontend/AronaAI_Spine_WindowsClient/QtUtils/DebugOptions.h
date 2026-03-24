#pragma once

#include <QObject>

class DebugOptions  : public QObject
{
	Q_OBJECT

public:
	DebugOptions(QObject *parent);
	~DebugOptions();
};

