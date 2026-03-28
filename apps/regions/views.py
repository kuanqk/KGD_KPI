from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.regions.models import Region
from apps.regions.serializers import RegionSerializer


class RegionListView(generics.ListAPIView):
    """
    GET /api/v1/regions/
    Возвращает полный справочник ДГД (20 регионов + КГД).
    Доступен всем аутентифицированным пользователям.
    Пагинация отключена — записей всего 21.
    """
    queryset = Region.objects.all().order_by('order')
    serializer_class = RegionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
