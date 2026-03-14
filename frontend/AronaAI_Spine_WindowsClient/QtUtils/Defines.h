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

#ifndef DEFINES_H
#define DEFINES_H

// 可爱的qDebug正常输出前缀
#define FINE_PR "ദ്ദി˶˃ ᵕ ˂ )✧ "

// 可爱的qWarning、qCritical错误输出前缀
#define ERROR_PR "૮₍ ˶•‸•˶₎ა "

// 获取Json->Json->String
#define GET_STRING_FROM_JSON(global_json, sec_json, trd_string) global_json->getJson(sec_json).getString(trd_string)

// 获取Json->Json->int
#define GET_INT_FROM_JSON(global_json, sec_json, trd_int) global_json->getJson(sec_json).getInt(trd_int)

// 获取Json->Json->double
#define GET_DOUBLE_FROM_JSON(global_json, sec_json, trd_double) global_json->getJson(sec_json).getDouble(trd_double)

// 获取Json->Json->bool
#define GET_BOOL_FROM_JSON(global_json, sec_json, trd_bool) global_json->getJson(sec_json).getBool(trd_bool)

// 获取全局缩放比例
#define WIDGET_ZOOM _global_config->getJson("settings").getDouble("zoom")

#endif // !DEFINES_H

