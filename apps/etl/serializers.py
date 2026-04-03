from rest_framework import serializers

from apps.etl.models import (
    ActiveInspection,
    CompletedInspection,
    ImportJob,
    ManualInput,
)


class ImportJobSerializer(serializers.ModelSerializer):
    """
    Сериализатор задачи импорта.
    При создании достаточно передать только 'source' (и опционально 'params').
    Все поля статуса и счётчики — read-only.
    """
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    started_by_display = serializers.StringRelatedField(source='started_by', read_only=True)

    class Meta:
        model = ImportJob
        fields = [
            'id',
            'source', 'source_display',
            'status', 'status_display',
            'started_by', 'started_by_display',
            'started_at', 'finished_at',
            'records_total', 'records_imported',
            'error_message',
            'params',
        ]
        read_only_fields = [
            'status', 'started_by',
            'started_at', 'finished_at',
            'records_total', 'records_imported',
            'error_message',
        ]


class CompletedInspectionSerializer(serializers.ModelSerializer):
    """
    Сериализатор завершённых проверок.
    Большинство полей — read-only (данные из ETL).
    Оператор может изменять только is_counted, is_accepted, is_anomaly.
    """
    region_display = serializers.StringRelatedField(source='region', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = CompletedInspection
        fields = [
            'id',
            'source', 'source_display',
            'source_id',
            'import_job',
            'region', 'region_display',
            'management', 'form_type',
            'completed_date',
            'amount_assessed', 'amount_collected',
            'is_counted', 'is_accepted', 'is_anomaly',
            'created_at',
        ]
        read_only_fields = [
            'source', 'source_id',
            'import_job', 'region',
            'management', 'form_type',
            'completed_date',
            'amount_assessed', 'amount_collected',
            'created_at',
        ]


class ActiveInspectionSerializer(serializers.ModelSerializer):
    """Сериализатор проводимых проверок — только чтение."""
    region_display = serializers.StringRelatedField(source='region', read_only=True)

    class Meta:
        model = ActiveInspection
        fields = [
            'id',
            'source', 'source_id',
            'import_job',
            'region', 'region_display',
            'management', 'case_type',
            'prescription_date',
            'is_counted',
        ]
        read_only_fields = fields


class ManualInputSerializer(serializers.ModelSerializer):
    """
    Сериализатор ручных вводов (доля КБК, штат).
    entered_by и entered_at заполняются автоматически.
    """
    region_display = serializers.StringRelatedField(source='region', read_only=True)
    entered_by_display = serializers.StringRelatedField(source='entered_by', read_only=True)

    class Meta:
        model = ManualInput
        fields = [
            'id',
            'region', 'region_display',
            'year',
            'kbk_share_pct',
            'staff_count',
            'entered_by', 'entered_by_display',
            'entered_at',
            'notes',
        ]
        read_only_fields = ['entered_by', 'entered_at']

    def validate(self, attrs):
        """Проверяем, что kbk_share_pct в диапазоне 0–100."""
        kbk = attrs.get('kbk_share_pct')
        if kbk is not None and not (0 <= kbk <= 100):
            raise serializers.ValidationError(
                {'kbk_share_pct': 'Доля КБК должна быть в диапазоне 0–100%.'}
            )
        return attrs
