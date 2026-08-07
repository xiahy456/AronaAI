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

#pragma once

#include <QWidget>
#include <QKeyEvent>
#include <QEvent>
#include <QResizeEvent>
#include <QRect>
#include <QSequentialAnimationGroup>
#include <QPropertyAnimation>
#include <QEasingCurve>
#include "ui_UserInputWidget.h"

#include "GlobalInclude.h"
#include "BlueakaFontLoader.h"

class UserInputWidget : public QWidget
{
	Q_OBJECT

public:
	UserInputWidget(QWidget *parent = nullptr);
	~UserInputWidget();

	void showForInput();

signals:
	void textSubmitted(const QString& text);

protected:
	void keyPressEvent(QKeyEvent* event) override;
	void changeEvent(QEvent* event) override;
	bool eventFilter(QObject* watched, QEvent* event) override;
	void resizeEvent(QResizeEvent* event) override;

private:
	Ui::UserInputWidgetClass ui;

	QRect m_normalGeometry;
	bool m_isSubmitting = false;
	QSequentialAnimationGroup* m_bounceAnimation = nullptr;

	void onReturnPressed();
	void playSubmitBounceAnimation();
	void syncChildrenGeometry();
	void stopBounceAndHide();
};
