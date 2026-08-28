from django.urls import path

from apps.organizations.views import (
    CityDetailView,
    CityListView,
    RegionDetailView,
    RegionListView,
    TrafficControlCenterDetailView,
    TrafficControlCenterListView,
)

app_name = "organizations"

urlpatterns = [
    path("regions/", RegionListView.as_view(), name="region-list"),
    path("regions/<int:region_id>/", RegionDetailView.as_view(), name="region-detail"),
    path("cities/", CityListView.as_view(), name="city-list"),
    path("cities/<int:city_id>/", CityDetailView.as_view(), name="city-detail"),
    path("control-centers/", TrafficControlCenterListView.as_view(), name="control-center-list"),
    path("control-centers/<int:center_id>/", TrafficControlCenterDetailView.as_view(), name="control-center-detail"),
]
