from django.contrib import admin

from .models import (
    CommandLog,
    Device,
    ModbusServerProfile,
    MqttClientProfile,
)

admin.site.register(Device)
admin.site.register(MqttClientProfile)
admin.site.register(ModbusServerProfile)
admin.site.register(CommandLog)
