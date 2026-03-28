from django.urls import path

from apps.regions.views import RegionListView

urlpatterns = [
    path('', RegionListView.as_view(), name='regions-list'),
]
