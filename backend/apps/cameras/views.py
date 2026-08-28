"""
Views for the cameras app.

RBAC (from rbac-matrix.md)
----
- System Administrator:    CRUD + health management
- Camera/Sensor Technician: CRUD + health management
- Traffic Control Officer: read-only
- Traffic Analyst:         read-only
- All other roles:         403
- Unauthenticated:         401
"""

import json
import os

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import StandardResultsPagination
from apps.common.responses import created_response, error_response, success_response
from apps.cameras.models import Camera, CameraHealth, CameraCredential, Sensor, SensorHealth
from apps.cameras.serializers import (
    CameraHealthSerializer, CameraHealthWriteSerializer,
    CameraSerializer, CameraWriteSerializer,
    SensorHealthSerializer, SensorHealthWriteSerializer,
    SensorSerializer, SensorWriteSerializer,
)
from apps.cameras.services import (
    CameraService, DuplicateCameraNameError,
    SensorService, DuplicateSensorNameError,
)
from apps.cameras.connectivity import test_camera_connection, CameraConnectionState

_READ_ROLES  = ["System Administrator", "Camera/Sensor Technician",
                "Traffic Control Officer", "Traffic Analyst"]
_WRITE_ROLES = ["System Administrator", "Camera/Sensor Technician"]


class _CameraPermission(IsAuthenticated):
    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        if request.user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user.groups.filter(name__in=_READ_ROLES).exists()
        return request.user.groups.filter(name__in=_WRITE_ROLES).exists()


# ---------------------------------------------------------------------------
# Camera list / create
# ---------------------------------------------------------------------------

class CameraListView(APIView):
    permission_classes = [_CameraPermission]

    def get(self, request: Request) -> Response:
        qs = Camera.objects.select_related("segment__road", "intersection").order_by("name")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if seg_id := request.query_params.get("segment"):
            qs = qs.filter(segment_id=seg_id)
        if int_id := request.query_params.get("intersection"):
            qs = qs.filter(intersection_id=int_id)
        if hs := request.query_params.get("health_status"):
            qs = qs.filter(health__health_status=hs)
        if cs := request.query_params.get("connectivity_status"):
            qs = qs.filter(health__connectivity_status=cs)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(CameraSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = CameraWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            data = dict(ser.validated_data)
            name = data.pop("name")
            camera_type = data.pop("camera_type", "fixed")
            camera = CameraService.create_camera(
                actor=request.user, name=name, camera_type=camera_type,
                request=request, **data,
            )
        except DuplicateCameraNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        camera = Camera.objects.select_related("segment__road", "intersection").get(pk=camera.pk)
        return created_response(data=CameraSerializer(camera).data,
                                message="Camera created successfully.")


# ---------------------------------------------------------------------------
# Camera detail / update
# ---------------------------------------------------------------------------

class CameraDetailView(APIView):
    permission_classes = [_CameraPermission]

    def _get(self, pk):
        return get_object_or_404(
            Camera.objects.select_related("segment__road", "intersection"), pk=pk
        )

    def get(self, request: Request, camera_id: int) -> Response:
        return success_response(data=CameraSerializer(self._get(camera_id)).data)

    def patch(self, request: Request, camera_id: int) -> Response:
        camera = self._get(camera_id)
        ser = CameraWriteSerializer(camera, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        fields.pop("name", None)  # name changes are allowed but go through service
        name = ser.validated_data.get("name")
        if name:
            fields["name"] = name
        try:
            camera = CameraService.update_camera(
                actor=request.user, camera=camera, request=request, **fields,
            )
        except DuplicateCameraNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        camera = Camera.objects.select_related("segment__road", "intersection").get(pk=camera.pk)
        return success_response(data=CameraSerializer(camera).data,
                                message="Camera updated successfully.")


class CameraStatusView(APIView):
    permission_classes = [_CameraPermission]

    def patch(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        camera = CameraService.set_camera_active(
            actor=request.user, camera=camera, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(
            data=CameraSerializer(Camera.objects.select_related("segment__road", "intersection").get(pk=camera.pk)).data,
            message=f"Camera '{camera.name}' {action}.",
        )


# ---------------------------------------------------------------------------
# Camera health — retrieve and upsert
# ---------------------------------------------------------------------------

class CameraHealthView(APIView):
    permission_classes = [_CameraPermission]

    def get(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        try:
            health = camera.health
        except CameraHealth.DoesNotExist:
            return error_response("No health record exists for this camera.",
                                  status_code=status.HTTP_404_NOT_FOUND)
        return success_response(data=CameraHealthSerializer(health).data)

    def put(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        ser = CameraHealthWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        health = CameraService.upsert_health(
            camera=camera,
            health_status=ser.validated_data["health_status"],
            connectivity_status=ser.validated_data["connectivity_status"],
            last_seen=ser.validated_data.get("last_seen"),
            detail=ser.validated_data.get("detail", ""),
        )
        return success_response(data=CameraHealthSerializer(health).data,
                                message="Camera health updated.")


# ---------------------------------------------------------------------------
# Sensor list / create
# ---------------------------------------------------------------------------

class SensorListView(APIView):
    permission_classes = [_CameraPermission]

    def get(self, request: Request) -> Response:
        qs = Sensor.objects.select_related("segment__road", "intersection").order_by("name")
        if request.query_params.get("active_only", "").lower() in ("1", "true"):
            qs = qs.filter(is_active=True)
        if seg_id := request.query_params.get("segment"):
            qs = qs.filter(segment_id=seg_id)
        if int_id := request.query_params.get("intersection"):
            qs = qs.filter(intersection_id=int_id)
        if hs := request.query_params.get("health_status"):
            qs = qs.filter(health__health_status=hs)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(SensorSerializer(page, many=True).data)

    def post(self, request: Request) -> Response:
        ser = SensorWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        try:
            data = dict(ser.validated_data)
            name = data.pop("name")
            sensor_type = data.pop("sensor_type", "other")
            sensor = SensorService.create_sensor(
                actor=request.user, name=name, sensor_type=sensor_type,
                request=request, **data,
            )
        except DuplicateSensorNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        sensor = Sensor.objects.select_related("segment__road", "intersection").get(pk=sensor.pk)
        return created_response(data=SensorSerializer(sensor).data,
                                message="Sensor created successfully.")


# ---------------------------------------------------------------------------
# Sensor detail / update
# ---------------------------------------------------------------------------

class SensorDetailView(APIView):
    permission_classes = [_CameraPermission]

    def _get(self, pk):
        return get_object_or_404(
            Sensor.objects.select_related("segment__road", "intersection"), pk=pk
        )

    def get(self, request: Request, sensor_id: int) -> Response:
        return success_response(data=SensorSerializer(self._get(sensor_id)).data)

    def patch(self, request: Request, sensor_id: int) -> Response:
        sensor = self._get(sensor_id)
        ser = SensorWriteSerializer(sensor, data=request.data, partial=True)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        fields = dict(ser.validated_data)
        try:
            sensor = SensorService.update_sensor(
                actor=request.user, sensor=sensor, request=request, **fields,
            )
        except DuplicateSensorNameError as exc:
            return error_response(str(exc), status_code=status.HTTP_400_BAD_REQUEST)
        sensor = Sensor.objects.select_related("segment__road", "intersection").get(pk=sensor.pk)
        return success_response(data=SensorSerializer(sensor).data,
                                message="Sensor updated successfully.")


class SensorStatusView(APIView):
    permission_classes = [_CameraPermission]

    def patch(self, request: Request, sensor_id: int) -> Response:
        sensor = get_object_or_404(Sensor, pk=sensor_id)
        is_active = request.data.get("is_active")
        if not isinstance(is_active, bool):
            return error_response("'is_active' must be a boolean.",
                                  status_code=status.HTTP_400_BAD_REQUEST)
        sensor = SensorService.set_sensor_active(
            actor=request.user, sensor=sensor, is_active=is_active, request=request,
        )
        action = "activated" if is_active else "deactivated"
        return success_response(
            data=SensorSerializer(Sensor.objects.select_related("segment__road", "intersection").get(pk=sensor.pk)).data,
            message=f"Sensor '{sensor.name}' {action}.",
        )


# ---------------------------------------------------------------------------
# Sensor health
# ---------------------------------------------------------------------------

class SensorHealthView(APIView):
    permission_classes = [_CameraPermission]

    def get(self, request: Request, sensor_id: int) -> Response:
        sensor = get_object_or_404(Sensor, pk=sensor_id)
        try:
            health = sensor.health
        except SensorHealth.DoesNotExist:
            return error_response("No health record exists for this sensor.",
                                  status_code=status.HTTP_404_NOT_FOUND)
        return success_response(data=SensorHealthSerializer(health).data)

    def put(self, request: Request, sensor_id: int) -> Response:
        sensor = get_object_or_404(Sensor, pk=sensor_id)
        ser = SensorHealthWriteSerializer(data=request.data)
        if not ser.is_valid():
            return error_response("Invalid data.", errors=ser.errors,
                                  status_code=status.HTTP_400_BAD_REQUEST)
        health = SensorService.upsert_health(
            sensor=sensor,
            health_status=ser.validated_data["health_status"],
            connectivity_status=ser.validated_data["connectivity_status"],
            last_seen=ser.validated_data.get("last_seen"),
            detail=ser.validated_data.get("detail", ""),
        )
        return success_response(data=SensorHealthSerializer(health).data,
                                message="Sensor health updated.")


# ---------------------------------------------------------------------------
# Camera connectivity test
# ---------------------------------------------------------------------------

class CameraTestView(APIView):
    """
    POST /api/v1/cameras/{id}/test/

    Performs a real connectivity test against the camera's RTSP endpoint.
    Returns one of 7 distinct states. Never fabricates a positive result.
    Never includes credential values in the response.
    Runs in a thread executor to avoid blocking the ASGI event loop.
    """
    permission_classes = [_CameraPermission]

    def post(self, request: Request, camera_id: int) -> Response:
        import concurrent.futures
        camera = get_object_or_404(
            Camera.objects.select_related("health"), pk=camera_id
        )
        # Run blocking I/O in thread pool — safe for ASGI (Daphne)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(test_camera_connection, camera)
            try:
                result = future.result(timeout=20)
            except concurrent.futures.TimeoutError:
                result = {
                    "state":       "rtsp_unreachable",
                    "state_label": "Test Timed Out",
                    "colour":      "red",
                    "detail":      "Connectivity test exceeded 20s timeout.",
                    "checked_at":  __import__('django.utils.timezone', fromlist=['timezone']).timezone.now().isoformat(),
                }

        # Update health record
        from apps.cameras.models import HealthStatus, ConnectivityStatus
        from django.utils import timezone

        state = result["state"]
        if state in ("live", "hls_available", "stream_connected", "ai_processing"):
            hs, cs = HealthStatus.HEALTHY, ConnectivityStatus.CONNECTED
        elif state == "auth_failed":
            hs, cs = HealthStatus.DEGRADED, ConnectivityStatus.CONNECTED
        elif state == "rtsp_unreachable":
            hs, cs = HealthStatus.OFFLINE, ConnectivityStatus.DISCONNECTED
        else:
            hs, cs = HealthStatus.UNKNOWN, ConnectivityStatus.UNKNOWN

        CameraHealth.objects.update_or_create(
            camera=camera,
            defaults={
                "health_status":       hs,
                "connectivity_status": cs,
                "last_seen":           timezone.now() if cs == ConnectivityStatus.CONNECTED else None,
                "checked_at":          timezone.now(),
                "detail":              result.get("detail", ""),
            },
        )
        return success_response(data=result)


# ---------------------------------------------------------------------------
# Camera credentials — write-only (never return password)
# ---------------------------------------------------------------------------

class CameraCredentialView(APIView):
    """
    PUT /api/v1/cameras/{id}/credentials/

    Store or update RTSP credentials for a camera.
    NEVER returns the password in any response.
    Restricted to System Admin and Camera Technician.
    """
    permission_classes = [_CameraPermission]

    def put(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        username = request.data.get("username", "")
        password = request.data.get("password", "")

        if not isinstance(username, str) or not isinstance(password, str):
            return error_response("username and password must be strings.",
                                  status_code=status.HTTP_400_BAD_REQUEST)

        from apps.cameras.models import CameraCredential
        from apps.audit.services import AuditAction, Outcome, log_audit_event

        cred, created = CameraCredential.objects.update_or_create(
            camera=camera,
            defaults={"username": username, "password": password},
        )

        log_audit_event(
            action=AuditAction.CAMERA_CREDENTIAL_SET if created else AuditAction.CAMERA_CREDENTIAL_ROTATED,
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
            target=camera,
            detail={
                "camera_id":   camera.pk,
                "camera_name": camera.name,
                "has_username": bool(username),
                # password deliberately excluded
            },
        )

        return success_response(data={
            "camera_id":    camera.pk,
            "camera_name":  camera.name,
            "has_credentials": bool(username),
            "action":       "created" if created else "updated",
        }, message="Credentials stored securely. Password is not returned.")

    def delete(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        from apps.cameras.models import CameraCredential
        try:
            camera.credential.delete()
            return success_response(data={"camera_id": camera.pk},
                                    message="Credentials removed.")
        except CameraCredential.DoesNotExist:
            return error_response("No credentials stored for this camera.",
                                  status_code=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Camera calibration (speed estimation)
# ---------------------------------------------------------------------------

class CameraCalibrationView(APIView):
    """
    GET  /api/v1/cameras/{id}/calibration/   Retrieve current calibration
    PUT  /api/v1/cameras/{id}/calibration/   Create or update calibration
    DELETE /api/v1/cameras/{id}/calibration/ Invalidate calibration

    Calibration data enables per-camera speed estimation.
    Without valid calibration, AI service stores avg_speed_kmh = NULL.
    """
    permission_classes = [_CameraPermission]

    def get(self, request: Request, camera_id: int) -> Response:
        camera = get_object_or_404(Camera, pk=camera_id)
        try:
            cal = camera.calibration
            return success_response(data={
                "camera_id":        camera.pk,
                "camera_name":      camera.name,
                "meters_per_pixel": cal.meters_per_pixel,
                "calibrated_at":    cal.calibrated_at.isoformat(),
                "is_valid":         cal.is_valid,
                "notes":            cal.notes,
            })
        except Exception:
            return success_response(data={
                "camera_id":        camera.pk,
                "camera_name":      camera.name,
                "meters_per_pixel": None,
                "calibrated_at":    None,
                "is_valid":         False,
                "notes":            "No calibration data. Speed estimation disabled.",
            })

    def put(self, request: Request, camera_id: int) -> Response:
        from apps.cameras.models import CameraCalibration
        from apps.audit.services import AuditAction, Outcome, log_audit_event

        camera = get_object_or_404(Camera, pk=camera_id)
        mpp = request.data.get("meters_per_pixel")
        notes = request.data.get("notes", "")

        if not mpp or float(mpp) <= 0:
            return error_response(
                "meters_per_pixel must be a positive number.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        cal, created = CameraCalibration.objects.update_or_create(
            camera=camera,
            defaults={
                "meters_per_pixel": float(mpp),
                "calibrated_by":    request.user,
                "notes":            notes,
                "is_valid":         True,
            }
        )
        log_audit_event(
            action="camera.calibration.set",
            outcome=Outcome.SUCCESS,
            request=request,
            actor=request.user,
            target=camera,
            detail={"camera_id": camera.pk, "meters_per_pixel": float(mpp)},
        )
        return success_response(data={
            "camera_id":        camera.pk,
            "meters_per_pixel": cal.meters_per_pixel,
            "is_valid":         cal.is_valid,
            "action":           "created" if created else "updated",
        }, message="Calibration saved. Speed estimation enabled.")

    def delete(self, request: Request, camera_id: int) -> Response:
        from apps.cameras.models import CameraCalibration
        camera = get_object_or_404(Camera, pk=camera_id)
        try:
            camera.calibration.is_valid = False
            camera.calibration.save(update_fields=["is_valid", "updated_at"])
            return success_response(data={"camera_id": camera.pk},
                                    message="Calibration invalidated. Speed estimation disabled.")
        except CameraCalibration.DoesNotExist:
            return error_response("No calibration found.", status_code=status.HTTP_404_NOT_FOUND)


# ---------------------------------------------------------------------------
# Upload Video Analysis endpoints (temporary user uploads)
# ---------------------------------------------------------------------------

class UploadVideoAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        f = request.FILES.get('file')
        if not f:
            return error_response('No file uploaded.', status_code=status.HTTP_400_BAD_REQUEST)
        from apps.cameras.models import TemporaryVideoAnalysis
        job = TemporaryVideoAnalysis.objects.create(
            user=request.user,
            original_filename=f.name,
            upload=f,
            status=TemporaryVideoAnalysis.STATUS_PENDING,
        )

        # Background processing: run the real video processor in a thread
        meters_pp = request.data.get('meters_per_pixel')
        try:
            meters_pp = float(meters_pp) if meters_pp is not None else None
        except Exception:
            meters_pp = None

        from apps.cameras.video_processor import process_video_job
        import threading
        t = threading.Thread(target=lambda: process_video_job(job, meters_pp), daemon=True)
        t.start()

        return created_response(data={'job_id': str(job.pk)}, message='Upload accepted. Processing started.')


class AnalysisStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, job_id: int) -> Response:
        from apps.cameras.models import TemporaryVideoAnalysis
        job = get_object_or_404(TemporaryVideoAnalysis, pk=job_id, user=request.user)
        data = {'job_id': job.pk, 'status': job.status, 'result': job.result_json}
        return success_response(data=data)


class AnalysisDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def _absolute_media_url(self, request: Request, path: str) -> str:
        if path.lower().startswith('http://') or path.lower().startswith('https://'):
            return path
        normalized = path.replace('\\', '/').lstrip('/')
        media_prefix = settings.MEDIA_URL.lstrip('/')
        if normalized.startswith(media_prefix):
            normalized = normalized[len(media_prefix):].lstrip('/')
        return request.build_absolute_uri(settings.MEDIA_URL.rstrip('/') + '/' + normalized)

    def get(self, request: Request, job_id: int) -> Response:
        from apps.cameras.models import TemporaryVideoAnalysis
        job = get_object_or_404(TemporaryVideoAnalysis, pk=job_id, user=request.user)
        if job.status != TemporaryVideoAnalysis.STATUS_DONE:
            return error_response('Job not completed yet.', status_code=status.HTTP_400_BAD_REQUEST)

        annotated = job.annotated_video.url if job.annotated_video else None
        if annotated:
            annotated = self._absolute_media_url(request, annotated)

        result = job.result_json or {}
        full_results = None
        try:
            results_file = result.get('results_file')
            if results_file:
                results_file = results_file.replace('\\', '/')
                full_path = os.path.join(settings.MEDIA_ROOT, results_file)
                if os.path.exists(full_path):
                    with open(full_path, 'r', encoding='utf8') as fh:
                        full_results = json.load(fh)
        except Exception:
            full_results = None

        if result.get('csv_file'):
            result['csv_url'] = self._absolute_media_url(request, result['csv_file'])
        elif result.get('csv_url'):
            result['csv_url'] = self._absolute_media_url(request, result['csv_url'])

        if result.get('pdf_file'):
            result['pdf_url'] = self._absolute_media_url(request, result['pdf_file'])
        elif result.get('pdf_url'):
            result['pdf_url'] = self._absolute_media_url(request, result['pdf_url'])

        if full_results and isinstance(full_results.get('snapshots'), list):
            for s in full_results['snapshots']:
                if s.get('image') or s.get('image_url'):
                    s['image_url'] = self._absolute_media_url(request, s.get('image_url') or s.get('image'))

        return success_response(data={'annotated_video': annotated, 'result': result, 'full_results': full_results})
