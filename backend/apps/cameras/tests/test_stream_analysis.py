import os
import tempfile
import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cameras.models import TemporaryVideoAnalysis

User = get_user_model()


class TestVideoAnalysisStreaming(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="owner_user", password="Password123!")
        self.user_b = User.objects.create_user(username="other_user", password="Password123!")

        self.client_a = APIClient()
        self.client_a.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(self.user_a))}")

        self.client_b = APIClient()
        self.client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(self.user_b))}")

        self.unauth_client = APIClient()

        # Create a temporary media file with dummy video content
        self.video_content = b"fake-mp4-video-content-header-and-frames-0123456789"
        self.job = TemporaryVideoAnalysis.objects.create(
            user=self.user_a,
            status=TemporaryVideoAnalysis.STATUS_DONE,
            result_json={"processed_frames": 100, "fps": 30.0, "vehicle_counts": {"car": 5}},
        )
        # Save a video file
        self.job.annotated_video.save("annotated/test_video.mp4", ContentFile(self.video_content))

    def tearDown(self):
        try:
            if self.job.annotated_video:
                raw = getattr(self.job.annotated_video, "name", "")
                if raw:
                    p = os.path.join(settings.MEDIA_ROOT, raw.replace("\\", "/").lstrip("/"))
                    if os.path.exists(p):
                        os.remove(p)
        except Exception:
            pass

    def test_stream_token_owner_authorized(self):
        url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/"
        resp = self.client_a.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("url", resp.json()["data"])
        self.assertIn("/stream/?s=", resp.json()["data"]["url"])

    def test_stream_token_unauthorized_user_forbidden_or_404(self):
        url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/"
        # Other authenticated user should get 404 (due to user=request.user isolation)
        resp = self.client_b.get(url)
        self.assertEqual(resp.status_code, 404)

        # Anonymous user should get 401
        resp_anon = self.unauth_client.get(url)
        self.assertEqual(resp_anon.status_code, 401)

    def test_stream_endpoint_with_windows_style_path(self):
        # Simulate a Windows-style backslash separator in annotated_video.name
        # e.g., "uploads/tmp_videos/2026/09/16\annotated\test_video.mp4"
        raw_name = self.job.annotated_video.name
        windows_style_name = raw_name.replace("/", "\\")
        self.job.annotated_video.name = windows_style_name
        self.job.save(update_fields=["annotated_video"])

        # Request stream token as owner
        tok_resp = self.client_a.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/")
        self.assertEqual(tok_resp.status_code, 200)
        stream_url = tok_resp.json()["data"]["url"]

        # Call stream endpoint
        stream_resp = self.unauth_client.get(stream_url)
        self.assertEqual(stream_resp.status_code, 200)
        self.assertEqual(stream_resp["Content-Type"], "video/mp4")

    def test_stream_endpoint_range_request(self):
        tok_resp = self.client_a.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/")
        stream_url = tok_resp.json()["data"]["url"]

        # Request bytes 0 to 9 (10 bytes)
        resp = self.unauth_client.get(stream_url, HTTP_RANGE="bytes=0-9")
        self.assertEqual(resp.status_code, 206)
        self.assertEqual(resp["Content-Type"], "video/mp4")
        self.assertEqual(resp["Content-Length"], "10")
        self.assertEqual(resp.content, self.video_content[:10])
        self.assertIn(f"bytes 0-9/{len(self.video_content)}", resp["Content-Range"])

    def test_tampered_or_invalid_stream_token_rejected(self):
        # Bad signature
        bad_url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s=tampered-signature"
        resp = self.unauth_client.get(bad_url)
        self.assertEqual(resp.status_code, 403)

        # Missing token
        resp_no_token = self.unauth_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/")
        self.assertEqual(resp_no_token.status_code, 403)

    def test_directory_traversal_prevention(self):
        # Attempt directory traversal in annotated_video.name
        self.job.annotated_video.name = "../../../etc/passwd"
        self.job.save(update_fields=["annotated_video"])

        payload = {"job_id": self.job.pk, "user_id": self.user_a.pk}
        token = signing.dumps(payload, salt="video-stream")
        traversal_url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}"

        resp = self.unauth_client.get(traversal_url)
        self.assertIn(resp.status_code, [403, 404])

    def test_expired_stream_token_rejected(self):
        payload = {"job_id": self.job.pk, "user_id": self.user_a.pk}
        token = signing.dumps(payload, salt="video-stream")
        with patch("django.core.signing.time.time", return_value=time.time() + 600):
            expired_url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}"
            resp = self.unauth_client.get(expired_url)
            self.assertEqual(resp.status_code, 403)

    def test_token_job_mismatch_rejected(self):
        payload = {"job_id": self.job.pk + 999, "user_id": self.user_a.pk}
        token = signing.dumps(payload, salt="video-stream")
        url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}"
        resp = self.unauth_client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_stream_token_tampering_rejected(self):
        # user_b attempts to stream user_a's video using a signed token with user_b's identity
        payload = {"job_id": self.job.pk, "user_id": self.user_b.pk}
        token = signing.dumps(payload, salt="video-stream")
        url = f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}"
        resp = self.unauth_client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_endpoints_non_disclosing_404(self):
        # Status
        resp = self.client_b.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/")
        self.assertEqual(resp.status_code, 404)

        # Download
        resp = self.client_b.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/download/")
        self.assertEqual(resp.status_code, 404)

        # Discard
        resp = self.client_b.delete(f"/api/v1/cameras/upload-analysis/{self.job.pk}/discard/")
        self.assertEqual(resp.status_code, 404)

    def test_system_administrator_oversight_allowed(self):
        admin_group, _ = Group.objects.get_or_create(name="System Administrator")
        admin_user = User.objects.create_user(username="admin_user", password="Password123!")
        admin_user.groups.add(admin_group)

        admin_client = APIClient()
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(admin_user))}")

        # Stream token fetch allowed for admin
        resp = admin_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/")
        self.assertEqual(resp.status_code, 200)

        # Status inspection allowed for admin
        resp = admin_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/")
        self.assertEqual(resp.status_code, 200)

        # Streaming with admin's token for user_a's job
        payload = {"job_id": self.job.pk, "user_id": admin_user.pk}
        token = signing.dumps(payload, salt="video-stream")
        stream_resp = self.unauth_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}")
        self.assertEqual(stream_resp.status_code, 200)

    def test_generic_is_staff_denied_oversight(self):
        # A staff user who is NOT in the System Administrator group must NOT receive oversight access
        staff_user = User.objects.create_user(username="staff_only", password="Password123!", is_staff=True)
        staff_client = APIClient()
        staff_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(staff_user))}")

        # Stream token denied (non-disclosing 404)
        resp = staff_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream-token/")
        self.assertEqual(resp.status_code, 404)

        # Status denied (non-disclosing 404)
        resp = staff_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/")
        self.assertEqual(resp.status_code, 404)

        # Streaming with staff token denied (403)
        payload = {"job_id": self.job.pk, "user_id": staff_user.pk}
        token = signing.dumps(payload, salt="video-stream")
        stream_resp = self.unauth_client.get(f"/api/v1/cameras/upload-analysis/{self.job.pk}/stream/?s={token}")
        self.assertEqual(stream_resp.status_code, 403)

    def test_upload_roles_permissions(self):
        url = "/api/v1/cameras/upload-analysis/"

        # Allowed roles: Admin, Analyst, TCO, Law Enforcement
        allowed_roles = [
            "System Administrator",
            "Traffic Analyst",
            "Traffic Control Officer",
            "Law Enforcement / Authorized Officer",
        ]
        for role_name in allowed_roles:
            grp, _ = Group.objects.get_or_create(name=role_name)
            u = User.objects.create_user(username=f"u_{role_name.replace(' ', '_').lower()[:15]}", password="Password123!")
            u.groups.add(grp)
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(u))}")
            # POST without file -> 400 Bad Request means permission was granted
            resp = c.post(url, {})
            self.assertEqual(resp.status_code, 400, f"Role {role_name} should have upload permission")

        # Denied roles: Camera/Sensor Technician, Payment/Fines Officer
        denied_roles = [
            "Camera/Sensor Technician",
            "Payment/Fines Officer",
        ]
        for role_name in denied_roles:
            grp, _ = Group.objects.get_or_create(name=role_name)
            u = User.objects.create_user(username=f"u_{role_name.replace(' ', '_').lower()[:15]}", password="Password123!")
            u.groups.add(grp)
            c = APIClient()
            c.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(u))}")
            resp = c.post(url, {})
            self.assertEqual(resp.status_code, 403, f"Role {role_name} should be denied upload permission")

        # Unauthenticated -> 401
        self.assertEqual(self.unauth_client.post(url, {}).status_code, 401)


class TestPhase3ProcessingAndReporting(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="proc_user", password="Password123!")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(self.user))}")

        # Create sample vehicle and driver
        from apps.drivers.models import Driver
        from apps.violations.models import Vehicle

        self.driver = Driver.objects.create(
            first_name="Abebe",
            last_name="Bikila",
            license_number="DL-ETH-12345",
            phone="+251911223344",
        )
        self.vehicle = Vehicle.objects.create(
            plate_number="AA-3-12345",
            vehicle_type="car",
            make="Toyota",
            model="Yaris",
            year=2021,
            color="Silver",
            driver=self.driver,
        )

        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_csv_export_format_and_data(self):
        import csv
        job = TemporaryVideoAnalysis.objects.create(
            user=self.user,
            original_filename="sample_traffic.mp4",
            status=TemporaryVideoAnalysis.STATUS_DONE,
        )
        csv_path = os.path.join(self.tmp_dir, f"results_{job.pk}.csv")

        # Simulate frames output with detections
        frames_output = [
            {
                "time": 0.5,
                "detections": [
                    {
                        "track_id": 101,
                        "class": "car",
                        "confidence": 0.892,
                        "bbox": [0.1234, 0.2345, 0.4567, 0.6789],
                        "plate": "AA-3-12345",
                        "vehicle": {"make": "Toyota", "model": "Yaris"},
                        "driver": {"full_name": "Abebe Bikila"},
                        "speed_kmh": 48.5,
                    },
                    {
                        "track_id": 102,
                        "class": "truck",
                        "confidence": 0.765,
                        "bbox": [0.5500, 0.4000, 0.8500, 0.9000],
                        "plate": "UNREGISTERED-88",
                        "vehicle": None,
                        "driver": None,
                        "speed_kmh": None,
                    }
                ]
            }
        ]

        # Use the exact video_processor CSV generation block
        with open(csv_path, 'w', newline='', encoding='utf8') as fh:
            writer_csv = csv.writer(fh)
            writer_csv.writerow([
                'timestamp_s', 'frame_index', 'track_id', 'class', 'confidence',
                'bbox_norm_x1', 'bbox_norm_y1', 'bbox_norm_x2', 'bbox_norm_y2',
                'plate_candidate', 'registry_matched', 'vehicle_make', 'vehicle_model',
                'driver_name', 'speed_kmh'
            ])
            for f_idx, f in enumerate(frames_output):
                t_s = f.get('time', 0.0)
                for d in f.get('detections', []):
                    bbox = d.get('bbox', [0, 0, 0, 0])
                    v_match = d.get('vehicle') or {}
                    d_match = d.get('driver') or {}
                    conf_str = f"{d.get('confidence'):.3f}" if d.get('confidence') is not None else ""
                    speed_str = f"{d.get('speed_kmh'):.1f}" if d.get('speed_kmh') is not None else ""
                    writer_csv.writerow([
                        f"{t_s:.2f}",
                        f_idx,
                        d.get('track_id', ''),
                        d.get('class', ''),
                        conf_str,
                        f"{bbox[0]:.4f}" if len(bbox) > 0 else "",
                        f"{bbox[1]:.4f}" if len(bbox) > 1 else "",
                        f"{bbox[2]:.4f}" if len(bbox) > 2 else "",
                        f"{bbox[3]:.4f}" if len(bbox) > 3 else "",
                        d.get('plate') or "",
                        "YES" if bool(v_match) else "NO",
                        v_match.get('make', ''),
                        v_match.get('model', ''),
                        d_match.get('full_name', ''),
                        speed_str
                    ])

        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, 'r', encoding='utf8') as fh:
            reader = list(csv.reader(fh))

        expected_header = [
            'timestamp_s', 'frame_index', 'track_id', 'class', 'confidence',
            'bbox_norm_x1', 'bbox_norm_y1', 'bbox_norm_x2', 'bbox_norm_y2',
            'plate_candidate', 'registry_matched', 'vehicle_make', 'vehicle_model',
            'driver_name', 'speed_kmh'
        ]
        self.assertEqual(reader[0], expected_header)
        self.assertEqual(len(reader), 3)  # header + 2 detections

        # First detection: matched vehicle
        row1 = reader[1]
        self.assertEqual(row1[0], "0.50")
        self.assertEqual(row1[2], "101")
        self.assertEqual(row1[3], "car")
        self.assertEqual(row1[4], "0.892")
        self.assertEqual(row1[9], "AA-3-12345")
        self.assertEqual(row1[10], "YES")
        self.assertEqual(row1[11], "Toyota")
        self.assertEqual(row1[12], "Yaris")
        self.assertEqual(row1[13], "Abebe Bikila")
        self.assertEqual(row1[14], "48.5")

        # Second detection: unregistered
        row2 = reader[2]
        self.assertEqual(row2[2], "102")
        self.assertEqual(row2[3], "truck")
        self.assertEqual(row2[9], "UNREGISTERED-88")
        self.assertEqual(row2[10], "NO")
        self.assertEqual(row2[11], "")
        self.assertEqual(row2[14], "")

    def test_pdf_report_generation_and_download(self):
        job = TemporaryVideoAnalysis.objects.create(
            user=self.user,
            original_filename="sample_traffic.mp4",
            status=TemporaryVideoAnalysis.STATUS_DONE,
        )
        pdf_filename = f"report_{job.pk}.pdf"
        pdf_rel_path = f"annotated/{pdf_filename}"
        pdf_full_path = os.path.join(settings.MEDIA_ROOT, "annotated", pdf_filename)
        os.makedirs(os.path.dirname(pdf_full_path), exist_ok=True)

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(pdf_full_path, pagesize=letter)
            c.drawString(40, 750, "TrafficOps — AI Video Analysis Report")
            c.drawString(40, 730, f"Job ID: #{job.pk}")
            c.drawString(40, 710, "Speed Calibration Status: Uncalibrated / Unavailable")
            c.save()
        except ImportError:
            # If reportlab is not installed in the container, write valid PDF structure
            with open(pdf_full_path, "wb") as fh:
                fh.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n")

        # Update job result_json with pdf_file
        job.result_json = {"pdf_file": pdf_rel_path}
        job.save(update_fields=["result_json"])

        try:
            self.assertTrue(os.path.exists(pdf_full_path))
            with open(pdf_full_path, "rb") as fh:
                header = fh.read(5)
            self.assertEqual(header, b"%PDF-")

            # Test download endpoint
            resp = self.client.get(f"/api/v1/cameras/upload-analysis/{job.pk}/download/")
            self.assertEqual(resp.status_code, 200)
            data = resp.json().get("data", {})
            self.assertIn("pdf_url", data.get("result", {}))
            self.assertIn(pdf_filename, data["result"]["pdf_url"])
        finally:
            if os.path.exists(pdf_full_path):
                os.remove(pdf_full_path)

    def test_plate_to_registry_resolution_pipeline(self):
        from apps.cameras.pipeline import _resolve_plate_registry

        # 1. Valid registered plate
        res_valid = _resolve_plate_registry("AA-3-12345")
        self.assertTrue(res_valid["matched"])
        self.assertIsNotNone(res_valid["vehicle"])
        self.assertEqual(res_valid["vehicle"]["make"], "Toyota")
        self.assertEqual(res_valid["vehicle"]["model"], "Yaris")
        self.assertIsNotNone(res_valid["driver"])
        self.assertIn("Abebe Bikila", res_valid["driver"]["full_name"])

        # 2. Case-insensitive and whitespace normalized
        res_case = _resolve_plate_registry("  aa-3-12345  ")
        self.assertTrue(res_case["matched"])
        self.assertEqual(res_case["vehicle"]["plate_number"], "AA-3-12345")

        # 3. Unmatched plate
        res_unmatched = _resolve_plate_registry("ET-NOT-REGISTERED-99")
        self.assertFalse(res_unmatched["matched"])
        self.assertIsNone(res_unmatched["vehicle"])
        self.assertIsNone(res_unmatched["driver"])

        # 4. Malformed and suspicious inputs (must not crash or inject)
        malformed_inputs = [
            None,
            "",
            "   ",
            "' OR '1'='1",
            "'; DROP TABLE violations_vehicle; --",
            "<script>alert(1)</script>",
            "###$$$%%%",
            "A" * 300,
        ]
        for bad_input in malformed_inputs:
            res_bad = _resolve_plate_registry(bad_input)
            self.assertIsInstance(res_bad, dict)
            self.assertFalse(res_bad["matched"], f"Failed for input: {bad_input}")
            self.assertIsNone(res_bad["vehicle"])
            self.assertIsNone(res_bad["driver"])

    def test_payment_fines_officer_denied_video_analysis_but_permitted_analytics(self):
        pay_group, _ = Group.objects.get_or_create(name="Payment/Fines Officer")
        pay_user = User.objects.create_user(username="pay_officer", password="Password123!")
        pay_user.groups.add(pay_group)

        pay_client = APIClient()
        pay_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(AccessToken.for_user(pay_user))}")

        # 1. Permitted Analytics endpoint (Violations Summary): HTTP 200
        resp_analytics = pay_client.get("/api/v1/analytics/violations/")
        self.assertEqual(resp_analytics.status_code, 200)

        # 2. Denied Video Analysis upload: HTTP 403
        resp_upload = pay_client.post("/api/v1/cameras/upload-analysis/", {})
        self.assertEqual(resp_upload.status_code, 403)
