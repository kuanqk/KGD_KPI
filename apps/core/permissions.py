"""
DRF-пермишены на основе ролей пользователя.
Используются во всех view вместо стандартных Django permissions.
"""
from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Доступ только для Администратора."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsOperator(BasePermission):
    """Доступ только для Оператора."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'operator'
        )


class IsReviewer(BasePermission):
    """Доступ только для Проверяющего."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'reviewer'
        )


class IsViewer(BasePermission):
    """Доступ только для Наблюдателя."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'viewer'
        )


class IsOperatorOrAdmin(BasePermission):
    """Доступ для Оператора или Администратора."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('operator', 'admin')
        )
