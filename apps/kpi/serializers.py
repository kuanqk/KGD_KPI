from rest_framework import serializers

from apps.kpi.models import KPIFormula, KPIResult, KPISummary


class KPIFormulaSerializer(serializers.ModelSerializer):
    """
    Сериализатор формулы KPI.
    При создании: version и created_by заполняются автоматически во ViewSet.
    is_active предыдущей версии автоматически снимается.
    """
    kpi_type_display = serializers.CharField(source='get_kpi_type_display', read_only=True)
    created_by_display = serializers.StringRelatedField(source='created_by', read_only=True)

    class Meta:
        model = KPIFormula
        fields = [
            'id',
            'kpi_type', 'kpi_type_display',
            'version',
            'config',
            'is_active',
            'created_by', 'created_by_display',
            'created_at',
            'notes',
        ]
        read_only_fields = ['version', 'created_by', 'created_at']


class KPIResultSerializer(serializers.ModelSerializer):
    """Результат расчёта одного KPI — только чтение."""
    region_display = serializers.StringRelatedField(source='region', read_only=True)
    kpi_type_display = serializers.CharField(source='get_kpi_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    calculated_by_display = serializers.StringRelatedField(source='calculated_by', read_only=True)

    class Meta:
        model = KPIResult
        fields = [
            'id',
            'region', 'region_display',
            'kpi_type', 'kpi_type_display',
            'formula',
            'date_from', 'date_to',
            'plan', 'fact', 'percent',
            'score',
            'calc_details',
            'status', 'status_display',
            'calculated_by', 'calculated_by_display',
            'calculated_at',
        ]
        read_only_fields = fields


class KPISummarySerializer(serializers.ModelSerializer):
    """Итоговый рейтинг ДГД за период — только чтение."""
    region_display = serializers.StringRelatedField(source='region', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = KPISummary
        fields = [
            'id',
            'region', 'region_display',
            'date_from', 'date_to',
            'score_assessment',
            'score_collection',
            'score_avg_assessment',
            'score_workload',
            'score_long_inspections',
            'score_cancelled',
            'score_total',
            'rank',
            'status', 'status_display',
            'calculated_at',
        ]
        read_only_fields = fields


class CalculateRequestSerializer(serializers.Serializer):
    """Входные параметры для POST /api/v1/kpi/calculate/."""
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    region_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_null=True,
        default=None,
        help_text='Список PK регионов. Null или пропустить — все ДГД.',
    )

    def validate(self, attrs):
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError(
                {'date_to': 'Дата окончания не может быть раньше даты начала.'}
            )
        return attrs
