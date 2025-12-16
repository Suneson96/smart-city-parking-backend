from django.http import JsonResponse
from prediction_app.api import predict_view as _predict_view

predict_view = _predict_view


def health_check(request):
    """Simple health check endpoint for Kubernetes probes."""
    return JsonResponse({"status": "healthy"})

