"""URL configuration for the cameras app."""

from django.urls import path

from apps.cameras.views import (
    CameraCalibrationView,
    CameraCredentialView,
    CameraDetailView, CameraHealthView, CameraListView,
    CameraStatusView, CameraTestView,
    SensorDetailView, SensorHealthView, SensorListView, SensorStatusView,
    UploadVideoAnalysisView, AnalysisStatusView, AnalysisDownloadView,
)

app_name = "cameras"

urlpatterns = [
    # Cameras — CRUD
    path("",                          CameraListView.as_view(),       name="camera-list"),
    path("<int:camera_id>/",          CameraDetailView.as_view(),     name="camera-detail"),
    path("<int:camera_id>/status/",   CameraStatusView.as_view(),     name="camera-status"),
    path("<int:camera_id>/health/",   CameraHealthView.as_view(),     name="camera-health"),

    # Phase 5 — connectivity test + credential management
    path("<int:camera_id>/test/",        CameraTestView.as_view(),       name="camera-test"),
    path("<int:camera_id>/credentials/", CameraCredentialView.as_view(), name="camera-credentials"),
    path("<int:camera_id>/calibration/", CameraCalibrationView.as_view(),name="camera-calibration"),

    # Sensors
    path("sensors/",                          SensorListView.as_view(),    name="sensor-list"),
    path("sensors/<int:sensor_id>/",          SensorDetailView.as_view(),  name="sensor-detail"),
    path("sensors/<int:sensor_id>/status/",   SensorStatusView.as_view(),  name="sensor-status"),
    path("sensors/<int:sensor_id>/health/",   SensorHealthView.as_view(),  name="sensor-health"),
    # Upload video analysis (temporary user uploads)
    path("upload-analysis/", UploadVideoAnalysisView.as_view(), name="upload-analysis"),
    path("upload-analysis/<int:job_id>/", AnalysisStatusView.as_view(), name="upload-analysis-status"),
    path("upload-analysis/<int:job_id>/download/", AnalysisDownloadView.as_view(), name="upload-analysis-download"),
]
