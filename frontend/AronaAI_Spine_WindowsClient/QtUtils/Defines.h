#ifndef DEFINES_H
#define DEFINES_H

// 可爱的qDebug正常输出前缀
#define FINE_PR "ദ്ദി˶˃ ᵕ ˂ )✧ "

// 可爱的qDebug错误输出前缀
#define ERROR_PR "૮₍ ˶•‸•˶₎ა "

// 获取Json->Json->String
#define GET_STRING_FROM_JSON(global_json, sec_json, trd_string) global_json->getJson(sec_json).getString(trd_string)

// 获取Json->Json->int
#define GET_INT_FROM_JSON(global_json, sec_json, trd_int) global_json->getJson(sec_json).getInt(trd_int)

#endif // !DEFINES_H

