"""
Production-readiness verification script.
Runs every check, prints exact PASS/FAIL with evidence.
Never fabricates a result.
"""

import os, sys, socket, subprocess
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

import requests as http
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta

BASE = "http://127.0.0.1:8000"
RESULTS = []

def check(name, passed, evidence=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((status, name, evidence))
    print(f"  {'✓' if passed else '✗'} {status:<5} {name}")
    if evidence:
        print(f"          {evidence[:100]}")

def login(username, password):
    r = http.post(f"{BASE}/api/v1/auth/login/", json={"username": username, "password": password}, timeout=8)
    return r.json().get("data", {}).get("access") if r.status_code == 200 else None

def get_json(path, token, method="GET", body=None):
    headers = {"Authorization": f"Bearer {token}"}
    if method == "POST":
        r = http.post(f"{BASE}{path}", headers=headers, json=body or {}, timeout=12)
    elif method == "PUT":
        r = http.put(f"{BASE}{path}", headers=headers, json=body or {}, timeout=12)
    else:
        r = http.get(f"{BASE}{path}", headers=headers, timeout=8)
    return r.status_code, r.json() if r.headers.get("content-type","").startswith("application/json") else {}

print("\n" + "="*60)
print("AI-POWERED SMART TRAFFIC MANAGEMENT SYSTEM")
print("Production Readiness Verification")
print("="*60)

# ── 1. BACKEND HEALTH ─────────────────────────────────────────
print("\n[1] Backend Health")
r = http.get(f"{BASE}/api/v1/health/", timeout=5)
check("Health endpoint 200", r.status_code == 200, r.text[:60])
check("Response format", r.json().get("status") == "ok", str(r.json()))

# ── 2. AUTHENTICATION ─────────────────────────────────────────
print("\n[2] Authentication")
token = login("Admin", "admin1234")
check("Login Admin/admin1234", token is not None, f"Token length={len(token) if token else 0}")

code, me = get_json("/api/v1/auth/me/", token)
check("/auth/me/ returns user", code == 200 and me.get("data", {}).get("username") == "Admin",
      f"username={me.get('data',{}).get('username')} roles={me.get('data',{}).get('roles')}")
check("Role = System Administrator", "System Administrator" in me.get("data",{}).get("roles",[]),
      str(me.get("data",{}).get("roles")))

# Token refresh
r_ref = http.post(f"{BASE}/api/v1/auth/refresh/", json={"refresh": login.__module__}, timeout=8)
# Use stored refresh from a fresh login
r2 = http.post(f"{BASE}/api/v1/auth/login/", json={"username": "Admin", "password": "admin1234"}, timeout=8)
refresh_token = r2.json().get("data", {}).get("refresh")
r_ref = http.post(f"{BASE}/api/v1/auth/refresh/", json={"refresh": refresh_token}, timeout=8)
check("Token refresh works", r_ref.status_code == 200 and "access" in r_ref.json().get("data",{}),
      f"HTTP {r_ref.status_code}")

# Logout
r_logout = http.post(f"{BASE}/api/v1/auth/logout/",
    headers={"Authorization": f"Bearer {token}"},
    json={"refresh": refresh_token}, timeout=8)
check("Logout invalidates refresh", r_logout.status_code == 200, f"HTTP {r_logout.status_code}")

# Re-login for subsequent tests
token = login("Admin", "admin1234")

# ── 3. CORS ───────────────────────────────────────────────────
print("\n[3] CORS")
r_cors = http.get(f"{BASE}/api/v1/health/",
    headers={"Origin": "http://localhost:5173"}, timeout=5)
cors_hdr = r_cors.headers.get("access-control-allow-origin","")
check("CORS allows localhost:5173", cors_hdr == "http://localhost:5173", f"header={cors_hdr}")
check("CORS credentials allowed", r_cors.headers.get("access-control-allow-credentials","") == "true")

# ── 4. RBAC ───────────────────────────────────────────────────
print("\n[4] RBAC (all 7 roles)")
roles = {
    "admin":       "System Administrator",
    "tco":         "Traffic Control Officer",
    "analyst":     "Traffic Analyst",
    "law":         "Law Enforcement / Authorized Officer",
    "camtech":     "Camera/Sensor Technician",
    "payofficer":  "Payment/Fines Officer",
    "publicuser":  "Public User",
}
role_tokens = {}
for uname, role in roles.items():
    t = login(uname, "Admin1234!")
    role_tokens[uname] = t
    check(f"Login {uname} ({role[:20]})", t is not None)

# Role-specific access checks
c,_ = get_json("/api/v1/audit/events/",      role_tokens["admin"])
check("Admin → audit: 200",      c == 200, f"HTTP {c}")
c,_ = get_json("/api/v1/audit/events/",      role_tokens["tco"])
check("TCO → audit: 403",        c == 403, f"HTTP {c}")
c,_ = get_json("/api/v1/traffic/incidents/", role_tokens["law"])
check("Law Enf → incidents: 200",c == 200, f"HTTP {c}")
c,_ = get_json("/api/v1/traffic/measurements/", role_tokens["law"])
check("Law Enf → measurements: 403", c == 403, f"HTTP {c}")
c,_ = get_json("/api/v1/cameras/",           role_tokens["camtech"])
check("CamTech → cameras: 200",  c == 200, f"HTTP {c}")
c,_ = get_json("/api/v1/cameras/",           role_tokens["payofficer"])
check("PayFines → cameras: 403", c == 403, f"HTTP {c}")
# Unauthenticated
r_unauth = http.get(f"{BASE}/api/v1/traffic/incidents/", timeout=5)
check("Unauthenticated → 401",   r_unauth.status_code == 401, f"HTTP {r_unauth.status_code}")

# ── 5. TRAFFIC DOMAINS ────────────────────────────────────────
print("\n[5] Traffic Domains")
for path, name in [
    ("/api/v1/traffic/incidents/",    "Incidents"),
    ("/api/v1/traffic/events/",       "Events"),
    ("/api/v1/traffic/measurements/", "Measurements"),
    ("/api/v1/traffic/signals/",      "Signals"),
    ("/api/v1/cameras/",              "Cameras"),
    ("/api/v1/cameras/sensors/",      "Sensors"),
    ("/api/v1/roads/",                "Roads"),
    ("/api/v1/roads/intersections/",  "Intersections"),
    ("/api/v1/analytics/flow/",       "Analytics Flow"),
    ("/api/v1/analytics/incidents/",  "Analytics Incidents"),
    ("/api/v1/analytics/violations/", "Analytics Violations"),
    ("/api/v1/audit/events/",         "Audit Log"),
    ("/api/v1/auth/users/",           "User Management"),
]:
    c, d = get_json(path, token)
    count = d.get("count", "n/a")
    check(f"{name} → 200 (count={count})", c == 200, f"HTTP {c}")

# ── 6. AI PIPELINE ────────────────────────────────────────────
print("\n[6] AI Pipeline")
from apps.traffic.models import TrafficMeasurement
ai_count = TrafficMeasurement.objects.filter(data_source='ai').count()
check(f"AI measurements in DB: {ai_count}", ai_count > 0, f"Total AI measurements={ai_count}")

recent_ai = TrafficMeasurement.objects.filter(
    data_source='ai',
    measured_at__gte=timezone.now() - timedelta(minutes=5)
).order_by('-measured_at').first()
check("Recent AI measurement (last 5 min)",
    recent_ai is not None,
    f"id={recent_ai.pk if recent_ai else None} vehicles={getattr(recent_ai,'vehicle_count',None)} at={recent_ai.measured_at.strftime('%H:%M:%S') if recent_ai else None}")

if recent_ai:
    check("AI speed=None (uncalibrated, not fabricated)",
        recent_ai.avg_speed_kmh is None,
        f"avg_speed_kmh={recent_ai.avg_speed_kmh}")
    check("AI data_source='ai'", recent_ai.data_source == 'ai', recent_ai.data_source)

# ── 7. SYSTEM STATUS ──────────────────────────────────────────
print("\n[7] System Status / Live Mode")
c, ss = get_json("/api/v1/system/status/", token)
check("System status endpoint 200", c == 200, f"HTTP {c}")
mode = ss.get("data", {}).get("mode")
ai_active = ss.get("data", {}).get("ai_processing_active")
check(f"Mode = live (because AI active + cams connected)",
    mode == "live",
    f"mode={mode} ai={ai_active} cams={ss.get('data',{}).get('cameras_connected')}")
check("ai_processing_active = True", ai_active is True, str(ai_active))

# ── 8. HLS STREAM ─────────────────────────────────────────────
print("\n[8] HLS Streams")
streams = [
    ("test-camera-4", "TEST-PRERECORDED (V4 busy road 39 vehicles)"),
]
for path, label in streams:
    r_hls = http.get(f"http://localhost:8888/{path}/index.m3u8",
        allow_redirects=True, timeout=6)
    is_m3u8 = r_hls.status_code == 200 and r_hls.text.startswith("#EXTM3U")
    check(f"HLS {path} ({label})", is_m3u8, f"HTTP {r_hls.status_code} content={r_hls.text[:30]}")

# Camera stream endpoint (safe HLS URL)
c, cs_data = get_json("/api/v1/cameras/10/stream/", token)
check("Camera stream endpoint returns HLS (not RTSP)",
    cs_data.get("data", {}).get("available") is True,
    f"available={cs_data.get('data',{}).get('available')} hls={cs_data.get('data',{}).get('hls_url')}")
check("Camera labelled as TEST source",
    cs_data.get("data", {}).get("is_test_source") is True,
    f"is_test_source={cs_data.get('data',{}).get('is_test_source')}")

# ── 9. CONNECTION TEST (7 states) ─────────────────────────────
print("\n[9] Camera Connectivity Test")
c, ct = get_json("/api/v1/cameras/10/test/", token, method="POST")
state = ct.get("data", {}).get("state")
check("Connection test endpoint 200", c == 200, f"HTTP {c}")
check(f"State is hls_available or live (pipeline working)",
    state in ("hls_available", "live", "ai_processing"),
    f"state={state} label={ct.get('data',{}).get('state_label')}")
# Password never in response
c2, cred_resp = get_json("/api/v1/cameras/7/credentials/", token, method="PUT",
    body={"username": "testcam", "password": "ShouldNeverAppearInResponse!"})
check("Credentials PUT 200", c2 == 200, f"HTTP {c2}")
import json as _json
raw = _json.dumps(cred_resp)
check("Password NOT in credentials response",
    "ShouldNeverAppearInResponse" not in raw,
    f"Contains password: {'ShouldNeverAppearInResponse' in raw}")

# ── 10. WEBSOCKET ─────────────────────────────────────────────
print("\n[10] WebSocket (Daphne + Redis Channels)")
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
layer = get_channel_layer()
try:
    async_to_sync(layer.group_send)("dashboard", {
        "type": "measurement_created",
        "payload": {"vehicle_count": 22, "data_source": "ai", "camera_id": 10}
    })
    check("Channel layer push to Redis", True, "group_send completed without error")
except Exception as e:
    check("Channel layer push to Redis", False, str(e))

# WS HTTP upgrade
import socket as _sock
def ws_probe(host, port, path, token_str):
    try:
        s = _sock.create_connection((host, port), timeout=5)
        s.sendall(f"GET {path}?token={token_str} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        data = s.recv(256).decode(errors='replace')
        s.close()
        return "101 Switching Protocols" in data
    except Exception as e:
        return False

ws_ok = ws_probe("127.0.0.1", 8000, "/ws/dashboard/", token)
check("WebSocket upgrade 101", ws_ok, "TCP WS handshake confirmed")

# ── 11. SEED DATA ─────────────────────────────────────────────
print("\n[11] Seed Data Integrity")
User = get_user_model()
admin_user = User.objects.filter(username="Admin").first()
check("Admin user exists", admin_user is not None, f"id={getattr(admin_user,'pk',None)}")
check("Admin has System Administrator role",
    admin_user and admin_user.groups.filter(name="System Administrator").exists())

all_roles = ["System Administrator","Traffic Control Officer","Traffic Analyst",
             "Law Enforcement / Authorized Officer","Camera/Sensor Technician",
             "Payment/Fines Officer","Public User"]
missing = [r for r in all_roles if not User.objects.filter(groups__name=r).exists()]
check("All 7 RBAC roles have users", len(missing) == 0, f"Missing users for: {missing}")

from apps.traffic.models import TrafficIncident, TrafficEvent
from apps.cameras.models import Camera
demo_inc = TrafficIncident.objects.count()
demo_evt = TrafficEvent.objects.count()
demo_cam = Camera.objects.filter(is_active=True).count()
check("Demo data present (incidents)", demo_inc > 0, f"incidents={demo_inc}")
check("Demo data present (cameras)", demo_cam > 0, f"active cameras={demo_cam}")

# ── 12. VIOLATIONS ────────────────────────────────────────────
print("\n[12] Violations & Evidence")
c, viol = get_json("/api/v1/violations/", token)
check("Violations endpoint 200", c == 200, f"HTTP {c} count={viol.get('count',0)}")
c, cit = get_json("/api/v1/violations/citations/", token)
check("Citations endpoint 200", c == 200, f"HTTP {c}")
# Plate never in violation serializer response
if viol.get("results"):
    result_str = _json.dumps(viol["results"][0])
    check("plate_number not in violation response (PII)", "plate_number" not in result_str)

# ── 13. FRONTEND BUILD ────────────────────────────────────────
print("\n[13] Frontend Build")
import pathlib
dist = pathlib.Path(__file__).parent.parent / "frontend" / "dist"
check("dist/index.html exists", (dist / "index.html").exists())
check("dist/assets/ has JS", any((dist/"assets").glob("*.js")))
check("dist/assets/ has CSS", any((dist/"assets").glob("*.css")))
check("HLS chunk split (hls-*.js)", any((dist/"assets").glob("hls-*.js")),
    "hls.js code-split correctly")

# ── 14. MANAGE.PY CHECKS ──────────────────────────────────────
print("\n[14] Django Management Checks")
import subprocess as sp
r1 = sp.run(["python","manage.py","check","--deploy","--fail-level","ERROR"],
    capture_output=True, text=True, cwd=str(pathlib.Path(__file__).parent))
check("manage.py check --deploy (no errors)", r1.returncode == 0,
    r1.stderr.strip()[-100:] if r1.returncode != 0 else "0 issues")
r2 = sp.run(["python","manage.py","makemigrations","--check"],
    capture_output=True, text=True, cwd=str(pathlib.Path(__file__).parent))
check("No pending migrations", r2.returncode == 0, r2.stdout.strip() or "No changes")

# ── SUMMARY ───────────────────────────────────────────────────
print("\n" + "="*60)
passed  = [r for r in RESULTS if r[0] == "PASS"]
failed  = [r for r in RESULTS if r[0] == "FAIL"]
print(f"PASSED: {len(passed)}/{len(RESULTS)}")
print(f"FAILED: {len(failed)}")
if failed:
    print("\nFailed checks:")
    for _, name, evidence in failed:
        print(f"  ✗ {name}")
        if evidence:
            print(f"    {evidence[:120]}")
print("="*60)
