from django.shortcuts import render
from django.http import HttpRequest, HttpResponse


def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Render telemetry dashboard based on existing API endpoints."""
    return render(request, "dashboard.html")
