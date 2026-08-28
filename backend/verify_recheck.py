"""
Re-verification of 6 previously failed checks.
All other checks already passed 57/63.
"""

import os, sys, socket
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.development'
import django; django.setup()

import requests as http
from django.utils import timezone
from datetime import timedelta

BASE = "http://127.0.0.1:8000"
RESULTS = []

def check(name, passed, evidence=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((status, name, evidence))
    sym = "✓" if passed else "✗"
    print(f"  {sym} {status:<5} {name}")
    if evidence:
        print(f"          {evidence[:120]}")

def login(u, p):
    r = http.post(f"{BASE}/api/v1/auth/login/", json={"username": u, "password": p}, timeout=8)
    d = r.json().get("data", {})
    return d.get("access"), d.get("refresh")

print("\n" + "="*60)
print("RE-VERIFICATION: 6 Previously Failed Checks")
print("="*60)

# Get fresh tokens
access, refresh = login("Admin", "admin1234")

# ── CHECK 1: Logout ───────────────────────────────────────────
print("\n[A] Logout invalidates refresh token")
# Use the FRESH refresh token for logout
r_logout = http.post(
    f"{BASE}/api/v1/auth/logout/",
    headers={"Authorization": f"Bearer {access}"},
    json={"refresh": refresh},
    timeout=8
)
check("Logout returns 200", r_logout.status_code == 200, f"HTTP {r_logout.status_code}")

# Verify the refresh token is now blacklisted (can't refresh again)
r_reuse = http.post(f"{BASE}/api/v1/auth/refresh/", json={"refresh": refresh}, timeout=8)
check("Refresh token blacklisted after logout",
    r_reuse.status_code in (401, 400),
    f"HTTP {r_reuse.status_code} — {r_reuse.text[:60]}")

# Re-login for rest of checks
access, refresh = login("Admin", "admin1234")

# ── CHECK 2: Recent AI measurement ────────────────────────────
print("\n[B] Recent AI measurement (last 5 min)")
from apps.traffic.models import TrafficMeasurement

recent = TrafficMeasurement.objects.filter(
    data_source='ai',
    measured_at__gte=timezone.now() - timedelta(minutes=5)
).order_by('-measured_at').first()

check("AI measurement exists in last 5 min",
    recent is not None,
    f"id={getattr(recent,'pk',None)} vehicles={getattr(recent,'vehicle_count',None)} at={recent.measured_at.strftime('%H:%M:%S UTC') if recent else 'None'}")

if recent:
    check("AI speed = None (uncalibrated, honest)",
        recent.avg_speed_kmh is None,
        f"avg_speed_kmh={recent.avg_speed_kmh}")
    check("AI data_source = 'ai'",
        recent.data_source == 'ai',
        recent.data_source)

total_ai = TrafficMeasurement.objects.filter(data_source='ai').count()
check(f"Total AI measurements in DB ({total_ai})", total_ai > 0, str(total_ai))

# ── CHECK 3 & 4: System Status ────────────────────────────────
print("\n[C] System Status — Live Mode")
r_ss = http.get(f"{BASE}/api/v1/system/status/",
    headers={"Authorization": f"Bearer {access}"}, timeout=8)
ss = r_ss.json().get("data", {})
mode = ss.get("mode")
ai_active = ss.get("ai_processing_active")
cams = ss.get("cameras_connected")

check(f"System mode = 'live' (mode={mode})",
    mode == "live",
    f"mode={mode} ai_active={ai_active} cams={cams} last_src={ss.get('last_measurement_source')}")
check("ai_processing_active = True",
    ai_active is True,
    f"ai_processing_active={ai_active}")

# ── CHECK 5: HLS stream ───────────────────────────────────────
print("\n[D] HLS Stream (test-camera-4)")
r_hls = http.get("http://localhost:8888/test-camera-4/index.m3u8",
    allow_redirects=True, timeout=8)
is_m3u8 = r_hls.status_code == 200 and r_hls.text.startswith("#EXTM3U")
check("HLS test-camera-4 returns M3U8 playlist",
    is_m3u8,
    f"HTTP {r_hls.status_code} content={r_hls.text[:60]}")

if is_m3u8:
    codec_hint = "avc1" in r_hls.text
    check("HLS playlist contains H264 codec (avc1)", codec_hint, r_hls.text[:120])

# ── CHECK 6: Connection test state ───────────────────────────
print("\n[E] Camera Connectivity Test — cam 10 (test-camera-4)")
r_ct = http.post(
    f"{BASE}/api/v1/cameras/10/test/",
    headers={"Authorization": f"Bearer {access}"},
    timeout=20
)
ct = r_ct.json().get("data", {})
state = ct.get("state")
check("Connection test returns 200", r_ct.status_code == 200, f"HTTP {r_ct.status_code}")
check("State is 'live', 'ai_processing', or 'hls_available'",
    state in ("live", "ai_processing", "hls_available"),
    f"state={state} label={ct.get('state_label')} detail={ct.get('detail','')[:80]}")
check("HLS URL in test response (safe — no RTSP credentials)",
    ct.get("hls_url") is not None,
    f"hls_url={ct.get('hls_url')}")

# ── PHYSICAL CCTV TEST ────────────────────────────────────────
print("\n[F] Physical CCTV Camera Test")
check("Physical CCTV camera tested",
    False,
    "NOT TESTED — No physical RTSP-compatible camera available in this environment. "
    "Architecture is ready: update Camera.stream_url to real RTSP URL, no code changes needed.")

# NOTE: Legacy persistent webcam record `WEBCAM-001` has been removed.
print("\n[G] PC Integrated Webcam Pipeline — legacy persistent webcam removed, use browser webcam test if needed.")

# ── SUMMARY ───────────────────────────────────────────────────
print("\n" + "="*60)
passed = [r for r in RESULTS if r[0] == "PASS"]
failed = [r for r in RESULTS if r[0] == "FAIL"]
print(f"Re-check PASSED: {len(passed)}/{len(RESULTS)}")
if failed:
    print("\nStill failing:")
    for _, name, evidence in failed:
        print(f"  ✗ {name}")
        if evidence:
            print(f"    → {evidence[:120]}")
print("="*60)
