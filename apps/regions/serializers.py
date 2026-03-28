from rest_framework import serializers

from apps.regions.models import Region


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'code', 'name_ru', 'name_kz', 'name_en', 'is_summary', 'order']
        read_only_fields = fields
