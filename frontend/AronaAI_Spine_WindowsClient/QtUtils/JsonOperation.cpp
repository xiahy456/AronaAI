#include <JsonOperation.h>

JsonOperation::JsonOperation()
{
    m_jsonObj = QJsonObject();
}

JsonOperation::JsonOperation(QString file_path)
{
	// 打开文件
	QFile file(file_path);
	if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
		qWarning().noquote() << ERROR_PR << "[Json Operation]Failed to open file: " << file_path;
		return;
	}
    qDebug().noquote() << FINE_PR << "[Json Operation]Open file succeed! Path: " << file_path;

	// 读取文件内容，解析为QByteArray对象
	QByteArray jsonData = file.readAll();

    // 关闭文件
    file.close();

    // 解析JSON数据
    QJsonParseError parseError;
    QJsonDocument jsonDoc = QJsonDocument::fromJson(jsonData, &parseError);

    // 检查解析是否成功
    if (parseError.error != QJsonParseError::NoError) {
        qWarning().noquote() << ERROR_PR << "[Json Operation]Failed to analsis file:" << parseError.errorString();
        qWarning().noquote() << ERROR_PR << "[Json Operation]Error at:" << parseError.offset;
        return;
    }
    if (jsonDoc.isNull() || !jsonDoc.isObject()) {
        qWarning().noquote() << ERROR_PR << "[Json Operation]Invailed json file!";
        return;
    }

    // 获取JSON对象并读取数据
    m_jsonObj = jsonDoc.object();

	// 输出调试信息
	qDebug().noquote() << FINE_PR << "[Json Operation]Successfully opened json file: " << file_path;
}

JsonOperation::JsonOperation(QJsonObject jsonObj)
{
	m_jsonObj = jsonObj;
}

JsonOperation::~JsonOperation()
{
}

QVariant JsonOperation::getValue(QString key)
{
	// 定义万能类QVariant对象value，接收JSON对象中对应key的value
    QVariant value;
	value = m_jsonObj[key].toVariant();

	// 返回value对象
    return value;
}

QString JsonOperation::getString(QString key)
{
    QJsonValue target_pair = m_jsonObj[key];
    // 判断是不是字符串并返回
    if (target_pair.isString()) return target_pair.toString();
    else {
        qWarning().noquote() << ERROR_PR << "[Qt Operation]Failed getting string! Target key: " << key;
        return "";
    }
}

int JsonOperation::getInt(QString key)
{
    int value = 0;
    value = m_jsonObj[key].toInt();
    return value;
}

double JsonOperation::getDouble(QString key)
{
    double value = 0.0;
    value = m_jsonObj[key].toDouble();
	return value;
}

bool JsonOperation::getBool(QString key)
{
	bool value = false;
	value = m_jsonObj[key].toBool();
	return value;
}


JsonOperation JsonOperation::getJson(QString key)
{
    QJsonValue target_pair = m_jsonObj[key];
    // 判断是不是Json并返回
    if (target_pair.isObject()) return target_pair.toObject();
    else {
        qWarning().noquote() << ERROR_PR << "[Qt Operation]Failed getting json object! Target key: " << key;
        return JsonOperation();
    }
}
