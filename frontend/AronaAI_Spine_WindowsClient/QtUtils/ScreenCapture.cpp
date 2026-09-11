/*
 Copyright 2026 xia_hy456. All rights reserved.

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

#include "ScreenCapture.h"
#include "Defines.h"

#include <QApplication>
#include <QBuffer>
#include <QCursor>
#include <QIODevice>
#include <QGuiApplication>
#include <QImage>
#include <QPixmap>
#include <QScreen>
#include <QThread>

#ifdef Q_OS_WIN
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dwmapi.h>
#ifndef WDA_EXCLUDEFROMCAPTURE
#define WDA_EXCLUDEFROMCAPTURE 0x00000011
#endif
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "dwmapi.lib")
#endif

namespace ScreenCapture {

#ifdef Q_OS_WIN
class ExcludeFromCaptureGuard
{
public:
	explicit ExcludeFromCaptureGuard(const QList<QWidget*>& widgets)
	{
		for (QWidget* widget : widgets) {
			if (!widget || !widget->isVisible()) {
				continue;
			}
			HWND hwnd = reinterpret_cast<HWND>(widget->winId());
			if (!hwnd) {
				continue;
			}
			const BOOL ok = SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE);
			m_hwnds.append(hwnd);
			m_applied.append(ok);
			if (!ok) {
				ERROR_DEBUG_OUTPUT(QString("[Screen Capture] WDA_EXCLUDEFROMCAPTURE failed hwnd=%1 err=%2")
					.arg(reinterpret_cast<quintptr>(hwnd))
					.arg(GetLastError()));
			}
		}
		DwmFlush();
		QApplication::processEvents();
		QThread::msleep(16);
	}

	~ExcludeFromCaptureGuard()
	{
		for (int i = 0; i < m_hwnds.size(); ++i) {
			if (m_applied.at(i)) {
				SetWindowDisplayAffinity(m_hwnds.at(i), WDA_NONE);
			}
		}
	}

private:
	QList<HWND> m_hwnds;
	QList<BOOL> m_applied;
};
#endif

QString grabJpegBase64(const QList<QWidget*>& excludeWindows)
{
#ifdef Q_OS_WIN
	ExcludeFromCaptureGuard guard(excludeWindows);
#else
	Q_UNUSED(excludeWindows);
#endif

	QScreen* screen = QGuiApplication::screenAt(QCursor::pos());
	if (!screen) {
		screen = QGuiApplication::primaryScreen();
	}
	if (!screen) {
		ERROR_DEBUG_OUTPUT("[Screen Capture] No screen available");
		return {};
	}

	const QPixmap pixmap = screen->grabWindow(0);
	if (pixmap.isNull()) {
		ERROR_DEBUG_OUTPUT("[Screen Capture] grabWindow returned null");
		return {};
	}

	QImage image = pixmap.toImage();
	const int maxWidth = 1280;
	if (image.width() > maxWidth) {
		image = image.scaledToWidth(maxWidth, Qt::SmoothTransformation);
	}

	QByteArray bytes;
	QBuffer buffer(&bytes);
	buffer.open(QIODevice::WriteOnly);
	if (!image.save(&buffer, "JPEG", 70)) {
		ERROR_DEBUG_OUTPUT("[Screen Capture] JPEG encode failed");
		return {};
	}

	FINE_DEBUG_OUTPUT(QString("[Screen Capture] Captured %1x%2 jpeg=%3 bytes")
		.arg(image.width())
		.arg(image.height())
		.arg(bytes.size()));
	return QString::fromLatin1(bytes.toBase64());
}

}
