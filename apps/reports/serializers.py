from rest_framework import serializers

from apps.kpi.serializers import KPISummarySerializer
from apps.reports.models import ReportApproval


class ReportApprovalSerializer(serializers.ModelSerializer):
    """История действий по утверждению отчёта."""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    actor_display = serializers.StringRelatedField(source='actor', read_only=True)

    class Meta:
        model = ReportApproval
        fields = [
            'id',
            'summary',
            'action', 'action_display',
            'actor', 'actor_display',
            'comment',
            'created_at',
        ]
        read_only_fields = ['actor', 'created_at']


class PendingSummarySerializer(KPISummarySerializer):
    """
    KPISummary для списка ожидающих утверждения.
    Расширяет базовый сериализатор историей действий.
    """
    approvals = ReportApprovalSerializer(many=True, read_only=True)

    class Meta(KPISummarySerializer.Meta):
        fields = KPISummarySerializer.Meta.fields + ['approvals']
        read_only_fields = fields


class ApprovalActionSerializer(serializers.Serializer):
    """Входные данные для действий approve / reject / recalculate."""
    comment = serializers.CharField(required=False, allow_blank=True, default='')
