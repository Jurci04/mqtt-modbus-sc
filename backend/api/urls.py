from django.urls import path

from .views import (
    DashboardSummaryView,
    ModbusQuotesView,
    MqttQuotesView,
    ServiceCommandView,
    ServiceStatusView,
)

urlpatterns = [
    path("mqtt/quotes/", MqttQuotesView.as_view(), name="mqtt-quotes"),
    path("modbus/quotes/", ModbusQuotesView.as_view(), name="modbus-quotes"),
    path(
        "dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"
    ),
    path(
        "service/<str:service_name>/command/",
        ServiceCommandView.as_view(),
        name="service-command",
    ),
    path(
        "service/<str:service_name>/status/",
        ServiceStatusView.as_view(),
        name="service-status",
    ),
]
