#include "BasicSettingsWidget.h"

BasicSettingsWidget::BasicSettingsWidget(QWidget *parent)
	: ParallelogramWidget(parent)
{
	ui.setupUi(this);

	// ¿Ø¼þ³õÊ¼»¯
	ui.frameRateLabel->move(240 * WIDGET_ZOOM, 20 * WIDGET_ZOOM);
	ui.frameRateLabel->resize(120 * WIDGET_ZOOM, 16 * WIDGET_ZOOM);
	LABEL_TEXT_INITIAL(ui.frameRateLabel, 12 * WIDGET_ZOOM, GET_STRING_FROM_JSON(_global_dict, "settings", "frame_rate"), "color: rgb(44, 69, 99); ");
}

BasicSettingsWidget::~BasicSettingsWidget()
{
}

