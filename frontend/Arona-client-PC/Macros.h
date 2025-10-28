#ifndef MACROS_H
#define MACROS_H

#endif // MACROS_H

// 翻译器初始化宏
#define TRANSLATOR_INITIALIZE(app_obj) do {\
    QTranslator translator; \
    const QStringList uiLanguages = QLocale::system().uiLanguages(); \
    for (const QString &locale : uiLanguages) { \
        const QString baseName = "Arona-client-PC_" + QLocale(locale).name(); \
        if (translator.load(":/i18n/" + baseName)) { \
            app_obj.installTranslator(&translator); \
            break; \
        } \
    } \
} while(0)
