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

#ifndef SCREENCAPTURE_H
#define SCREENCAPTURE_H

#include <QList>
#include <QString>
#include <QWidget>

namespace ScreenCapture {

// Grab the screen under the cursor as JPEG base64.
// excludeWindows are omitted from the bitmap via WDA_EXCLUDEFROMCAPTURE
// (still visible to the user). Empty string on failure.
QString grabJpegBase64(const QList<QWidget*>& excludeWindows);

}

#endif // SCREENCAPTURE_H
