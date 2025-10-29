#pragma once

#include <QWidget>
#include <QOpenGLWidget>

class GLCore : public QOpenGLWidget
{
	Q_OBJECT
public:
	GLCore(QWidget* parent = nullptr);
	~GLCore();

protected:
	void initializeGL() override;
	void resizeGL(int w, int h) override;
	void paintGL() override;

};