from rest_framework import serializers

from apps.core.models import AuditLog, User
from apps.regions.models import Region


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор для управления учётными записями (только Администратор).
    Пароль — write-only. При обновлении пароль необязателен.
    """
    password = serializers.CharField(
        write_only=True, required=False, min_length=8,
        style={'input_type': 'password'},
    )
    region_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Region.objects.all(),
        source='regions',
        required=False,
        help_text='Привязка к регионам (актуально для Наблюдателя)',
    )
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email',
            'first_name', 'last_name',
            'role', 'role_display',
            'mac_address',
            'is_active',
            'password',
            'region_ids',
            'date_joined',
            'last_login',
        ]
        read_only_fields = ['date_joined', 'last_login']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        regions = validated_data.pop('regions', [])
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if regions:
            user.regions.set(regions)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        regions = validated_data.pop('regions', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if regions is not None:
            instance.regions.set(regions)
        return instance


class AuditLogSerializer(serializers.ModelSerializer):
    """Сериализатор аудит-лога — только чтение."""
    user_display = serializers.StringRelatedField(source='user', read_only=True)
    event_display = serializers.CharField(source='get_event_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_display',
            'event', 'event_display',
            'details',
            'ip_address', 'mac_address',
            'created_at',
        ]
        read_only_fields = fields
