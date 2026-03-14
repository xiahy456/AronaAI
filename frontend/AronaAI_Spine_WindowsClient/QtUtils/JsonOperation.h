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

#ifndef JSONOPERATION_H
#define JSONOPERATION_H

#include <Defines.h>

#include <QFile>          // 文件操作
#include <QJsonDocument>  // JSON文档
#include <QJsonObject>    // JSON对象
#include <QJsonParseError> // 错误处理
#include <QJsonValue>
#include <QDebug>         // 调试输出

class JsonOperation {
public:
	// 构造函数
	// 无参数构造
	JsonOperation();
	// 传入文件路径
	JsonOperation(QString file_path);
	// 直接传入Json对象
	JsonOperation(QJsonObject jsonObj);
	
	// 析构函数
	~JsonOperation();

	// 通过key，获取该Json文件中对应的value值
	QVariant getValue(QString key);

	// 直接获取QString类型数据
	QString getString(QString key);

	// 直接获取int类型数据
	int getInt(QString key);

	// 直接获取double类型数据
	double getDouble(QString key);

	// 直接获取bool类型数据
	bool getBool(QString key);

	// 直接获取Json类型数据
	JsonOperation getJson(QString key);

	QVariant static analysisJson(QString json, QString key);

	// JSON对象
	QJsonObject m_jsonObj;

};

#endif // JSONOPERATION_H