from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Лёгкий эндпоинт для Docker healthcheck и балансировщиков. Без БД, без JWT."""
    return JsonResponse({"status": "ok"})
