"""
Вью для аутентификации и управления пользователями.

Аутентификация:
  POST /api/v1/auth/login/   → JWT access + refresh
  POST /api/v1/auth/logout/  → логирует выход

Управление пользователями (только Администратор — /api/v1/admin/):
  UserViewSet      — CRUD
  AuditLogViewSet  — read-only
"""
import logging

from django_ratelimit.core import is_ratelimited
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.models import AuditLog, User
from apps.core.permissions import IsAdmin
from apps.core.serializers import AuditLogSerializer, UserSerializer

logger = logging.getLogger(__name__)


def _get_ip(request) -> str | None:
    """Извлекает IP-адрес клиента (учитывает X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# Аутентификация
# ---------------------------------------------------------------------------

class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/
    Body: {"username": "...", "password": "..."}
    Возвращает: {"access": "...", "refresh": "..."}
    Записывает событие 'login' в AuditLog.
    Rate limit: 5 запросов/минуту по IP (429 при превышении).
    """

    def post(self, request, *args, **kwargs):
        # django-ratelimit 4.x: обязателен аргумент group или fn
        if is_ratelimited(
            request,
            group='auth_login',
            key='ip',
            rate='5/m',
            method='POST',
            increment=True,
        ):
            logger.warning(
                'LoginView: rate limit exceeded ip=%s', _get_ip(request)
            )
            return Response(
                {'detail': 'Слишком много попыток входа. Подождите минуту.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            try:
                user = User.objects.get(username=request.data.get('username'))
                AuditLog.log(
                    event='login',
                    user=user,
                    ip_address=_get_ip(request),
                )
            except User.DoesNotExist:
                pass
        return response


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Body (необязательно): {"refresh": "..."}  — для инвалидации токена на клиенте
    Записывает событие 'logout' в AuditLog.
    JWT — stateless: клиент должен удалить токены у себя.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        AuditLog.log(
            event='logout',
            user=request.user,
            ip_address=_get_ip(request),
        )
        return Response({'detail': 'Вы успешно вышли.'}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Управление пользователями (Администратор)
# ---------------------------------------------------------------------------

class _AuditLogPagination(CursorPagination):
    page_size = 50
    ordering = '-created_at'


class UserViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/v1/admin/users/       — список пользователей
    POST   /api/v1/admin/users/       — создать пользователя
    GET    /api/v1/admin/users/{id}/  — детали
    PUT    /api/v1/admin/users/{id}/  — обновить
    PATCH  /api/v1/admin/users/{id}/  — частичное обновление
    DELETE /api/v1/admin/users/{id}/  — удалить (деактивировать)

    Доступно только Администратору.
    """
    queryset = User.objects.select_related().prefetch_related('regions').order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    pagination_class = None  # список пользователей небольшой

    def perform_create(self, serializer):
        user = serializer.save()
        AuditLog.log(
            event='user_mgmt',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'create',
                'target_user_id': user.pk,
                'target_username': user.username,
                'role': user.role,
            },
        )

    def perform_update(self, serializer):
        user = serializer.save()
        AuditLog.log(
            event='user_mgmt',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'update',
                'target_user_id': user.pk,
                'target_username': user.username,
            },
        )

    def perform_destroy(self, instance):
        AuditLog.log(
            event='user_mgmt',
            user=self.request.user,
            ip_address=_get_ip(self.request),
            details={
                'action': 'delete',
                'target_user_id': instance.pk,
                'target_username': instance.username,
            },
        )
        instance.delete()


class AuditLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET /api/v1/admin/audit-logs/       — список событий (cursor pagination)
    GET /api/v1/admin/audit-logs/{id}/  — детали события

    Доступно только Администратору.
    Поддерживает фильтрацию по ?event= и ?user=
    """
    queryset = (
        AuditLog.objects
        .select_related('user')
        .order_by('-created_at')
    )
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    pagination_class = _AuditLogPagination
    filterset_fields = ['event', 'user']
