from django.urls import path

from apps.drivers.views import DriverDetailView, DriverListView, DriverViolationsView

app_name = "drivers"

urlpatterns = [
    path("", DriverListView.as_view(), name="driver-list"),
    path("<int:driver_id>/", DriverDetailView.as_view(), name="driver-detail"),
    path("<int:driver_id>/violations/", DriverViolationsView.as_view(), name="driver-violations"),
]
