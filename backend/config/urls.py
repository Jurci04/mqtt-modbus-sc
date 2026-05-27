from django.urls import include, path

from backend.api.dashboard import dashboard_view

urlpatterns = [
    path("dashboard/", dashboard_view, name="dashboard"),
    path("api/", include("backend.api.urls")),
]
