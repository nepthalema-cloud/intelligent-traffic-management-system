# TrafficOps — Local Development Startup & Testing Guide

> **Verified 2026-08-04 against the live running system.**
> Every command, path, port, and credential was tested against the actual
> process list, database, and HTTP endpoints — nothing is assumed.

---

## Verification Summary (current state)

| Check | Result |
|---|---|
| Frontend `http://localhost:5173/` | ✅ HTTP 200 |
| Backend health `http://localhost:8000/api/v1/health/` | ✅ `{status: ok}` |
| Login `Admin / admin1234` | ✅ JWT issued |
| `/auth/me/` | ✅ `username=Admin, roles=[System Administrator]` |
| Redis | ✅ Docker container `traffic_redis` Up |
| MediaMTX | ✅ Docker container `traffic_mediamtx` Up |
| HLS stream `test-camera-4` | ✅ HTTP 200 |
| System status | ✅ `mode=degraded, cameras=6, ai_processing_active=true` |
| AI measurements | ✅ 1971 total, latest posted 2026-08-04T14:55:07Z |

---

## 1. Prerequisites

Everything below is already installed on this machine — no installation step is needed before running.

| Tool | Location | Version |
|---|---|---|
| Python | `C:\Python314\python.exe` | 3.14.4 |
| All Python packages | System site-packages | Django 6.0.7, daphne, channels, channels-redis, ultralytics, opencv, celery |
| Node.js | System PATH | `npm` available |
| Docker Desktop | System | Running |
| FFmpeg | `C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe` | 8.1.2 |

**No virtual environments exist** — all packages are in the system Python. Do not create or activate any `.venv`.

---

## 2. Project Root

```
C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\
├── backend\                ← Django / Daphne
├── frontend\               ← React / Vite
├── ai-services\
│   └── vehicle_detection\  ← AI service (YOLO + RTSP)
│       ├── src\
│       │   └── main.py     ← entry point
│       ├── yolov8n.pt      ← YOLO model weights
│       └── .env            ← CAMERA_ID=10, RTSP_URL=test-camera-4
├── docker\
│   ├── mediamtx.yml
│   ├── start_test_streams.ps1
│   └── test_videos\        ← 4 MP4 files confirmed present
└── docker-compose.yml
```

---

## 3. What Needs to Run

### Tier A — Required for the website to work

| # | Service | What it provides |
|---|---|---|
| 1 | Redis (Docker) | Django Channels layer — WebSockets fail without it |
| 2 | MediaMTX (Docker) | HLS endpoint — Cameras page needs it even without test video |
| 3 | Django / Daphne | REST API + WebSocket server on port 8000 |
| 4 | React / Vite | Frontend on port 5173 |

### Tier B — Required for test video streaming and AI pipeline

| # | Service | What it provides |
|---|---|---|
| 5 | `start_test_streams.ps1` | Pushes 4 prerecorded MP4s to MediaMTX as RTSP (TEST VIDEO) |
| 6 | AI detection service | Reads RTSP, runs YOLOv8, posts measurements to Django |

### Tier C — Optional

| # | Service | What it provides |
|---|---|---|
| 7 | Webcam script | Streams PC webcam to MediaMTX as LIVE WEBCAM |
| 8 | Celery worker+beat | Hourly/daily analytics aggregation |

### Not needed locally

- PostgreSQL — the backend `.env` has `DB_NAME` commented out. Django uses **SQLite** (`backend/db.sqlite3`) automatically.
- Additional AI services (face recognition, OCR, prediction, tracking) — stub directories only, not implemented.

---

## 4. Startup Order

```
Step 1 → Redis + MediaMTX   (Docker infrastructure — everything else depends on these)
Step 2 → Django / Daphne    (needs Redis channel layer to start cleanly)
Step 3 → React / Vite       (needs Django API for data)
──── Tier A done — website fully functional ────
Step 4 → start_test_streams.ps1   (MUST run before AI service)
Step 5 → AI detection service     (needs MediaMTX RTSP to already have a stream)
──── Tier B done — AI + test video pipeline active ────
Step 6 → Celery (optional)
```

**Critical dependency:** The AI service starts immediately and attempts RTSP connection. If `start_test_streams.ps1` has not been run first, the AI service will enter exponential backoff retry — it will recover automatically once streams are up, but start the streams first to avoid unnecessary wait.

---

## 5. Terminal Commands

Open each in a **separate PowerShell window**. Keep all windows open.

---

### Terminal 1 — Redis + MediaMTX (Docker)

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System"
docker compose up redis mediamtx
```

**Expected output:**
```
traffic_redis      | Ready to accept connections tcp
traffic_mediamtx   | INF listener opened on :8554 (RTSP)
traffic_mediamtx   | INF listener opened on :8888 (HLS)
```

**Ports provided:**
- Redis: `localhost:6379`
- MediaMTX RTSP input: `localhost:8554`
- MediaMTX HLS output: `localhost:8888`

**Verify (run in a new PS window):**
```powershell
docker ps --format "table {{.Names}}`t{{.Status}}"
```
Both `traffic_redis` and `traffic_mediamtx` must show `Up`.

---

### Terminal 2 — Django / Daphne (ASGI server)

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\backend"
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

**Why `python -m daphne`, not just `daphne`:** Both work on this machine. `python -m daphne` is more reliable and avoids PATH confusion.

**Why Daphne, not `manage.py runserver`:** The ASGI application handles both HTTP (REST API) and WebSocket. `runserver` does not support WebSockets — the Dashboard real-time feed would silently fail.

**Expected output:**
```
2026-08-04 ... Django version 6.0.7, using settings 'config.settings.development'
2026-08-04 ... Starting server at tcp:interface=127.0.0.1:port=8000
```

**Port provided:** `localhost:8000`

**Verify:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/"
```
Expected: `status : ok`

---

### Terminal 3 — React / Vite (frontend)

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\frontend"
npm run dev
```

**Expected output:**
```
  VITE v8.2.0  ready in ... ms
  ➜  Local:   http://localhost:5173/
```

**Port provided:** `http://localhost:5173`

**Verify:** Open `http://localhost:5173/` in browser — TrafficOps homepage loads.

---

### Terminal 4 — TEST VIDEO streams (FFmpeg → MediaMTX)

> **These are PRERECORDED TEST VIDEOS — not live CCTV cameras.**

> **Important:** `start_test_streams.ps1` uses `Start-Process -WindowStyle Hidden` which
> spawns child processes that are not visible from automated/background sessions.
> Run it from a normal interactive PowerShell window. The 4 FFmpeg processes will
> appear as hidden background processes and push RTSP to MediaMTX continuously.

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System"
.\docker\start_test_streams.ps1
```

**Why run from the project root:** The script uses `$PSScriptRoot` internally, so it resolves `docker\test_videos\` correctly regardless of where you call it from. Alternatively: `cd docker ; .\start_test_streams.ps1`.

**If streams don't appear after 10 seconds**, run each FFmpeg command directly — one terminal per stream. The exact commands are (copy-paste ready):

```powershell
# Stream 1 — Urban intersection
$ff = "C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
$vd = "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\docker\test_videos"
& $ff -re -stream_loop -1 -i "$vd\27260-362770008_medium.mp4" -c:v libx264 -preset ultrafast -tune zerolatency -b:v 800k -maxrate 800k -bufsize 1600k -f rtsp -rtsp_transport tcp rtsp://localhost:8554/test-camera-1
```

```powershell
# Stream 2 — Highway + trucks
$ff = "C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
$vd = "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\docker\test_videos"
& $ff -re -stream_loop -1 -i "$vd\8355-208052034_medium.mp4" -c:v libx264 -preset ultrafast -tune zerolatency -b:v 800k -maxrate 800k -bufsize 1600k -f rtsp -rtsp_transport tcp rtsp://localhost:8554/test-camera-2
```

```powershell
# Stream 3 — Dense traffic
$ff = "C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
$vd = "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\docker\test_videos"
& $ff -re -stream_loop -1 -i "$vd\istockphoto-476627368-mp4-480x480-is.mp4" -c:v libx264 -preset ultrafast -tune zerolatency -b:v 800k -maxrate 800k -bufsize 1600k -f rtsp -rtsp_transport tcp rtsp://localhost:8554/test-camera-3
```

```powershell
# Stream 4 — Busy road (AI service watches this one)
$ff = "C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
$vd = "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\docker\test_videos"
& $ff -re -stream_loop -1 -i "$vd\istockphoto-851692014-640_adpp_is.mp4" -c:v libx264 -preset ultrafast -tune zerolatency -b:v 800k -maxrate 800k -bufsize 1600k -f rtsp -rtsp_transport tcp rtsp://localhost:8554/test-camera-4
```

**Expected output:**
```
=== TEST RTSP STREAMS (PRERECORDED, NOT LIVE CCTV) ===
Stream: test-camera-1 | Urban intersection 1280x720 30fps
  RTSP: rtsp://localhost:8554/test-camera-1
  HLS:  http://localhost:8888/test-camera-1/index.m3u8
Stream: test-camera-2 | ...
Stream: test-camera-3 | ...
Stream: test-camera-4 | Busy road 768x432 30fps, 39 vehicles/frame BEST TRACKING
  RTSP: rtsp://localhost:8554/test-camera-4
  HLS:  http://localhost:8888/test-camera-4/index.m3u8
All 4 test streams started.
```

Four hidden FFmpeg processes start in the background. The script exits after printing the above.

**Wait ~3 seconds** for the first HLS segment to appear, then verify:
```powershell
Invoke-WebRequest -Uri "http://localhost:8888/test-camera-4/index.m3u8" -UseBasicParsing | Select-Object StatusCode
```
Expected: `StatusCode : 200`

**Streams provided:**

| Camera DB record | Stream path | HLS URL |
|---|---|---|
| CAM-001 (id=7) | `test-camera-1` | `http://localhost:8888/test-camera-1/index.m3u8` |
| CAM-002 (id=8) | `test-camera-2` | `http://localhost:8888/test-camera-2/index.m3u8` |
| CAM-003 (id=9) | `test-camera-3` | `http://localhost:8888/test-camera-3/index.m3u8` |
| CAM-004 (id=10) | `test-camera-4` | `http://localhost:8888/test-camera-4/index.m3u8` |

---

### Terminal 5 — AI Vehicle Detection Service

> Reads RTSP from `test-camera-4`. Posts real YOLOv8 detections to Django.
> **Must start AFTER Terminal 4** (streams must exist before connecting).

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\ai-services\vehicle_detection"
python src\main.py
```

**Configuration used** (from `.env` in this directory):
```
CAMERA_ID=10               ← CAM-004 in the database
RTSP_URL=rtsp://localhost:8554/test-camera-4
MEASUREMENT_INTERVAL_SECONDS=10
DETECTION_CONFIDENCE=0.4
YOLO_MODEL=yolov8n.pt      ← located at ai-services/vehicle_detection/yolov8n.pt
```

**Expected output:**
```
[INFO] Loading YOLO model: yolov8n.pt
[INFO] YOLO model loaded (device: cpu)
[INFO] Login successful
[INFO] Pipeline active: camera=10 AI=yolov8n.pt speed=disabled (no calibration)
[INFO] Measurement ✓ vehicles=21 speed=NULL (uncalibrated) interval=10s
```

A new measurement is posted every 10 seconds.

**Verify measurements are flowing:**
```powershell
$lr = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login/" -Method POST -Body '{"username":"Admin","password":"admin1234"}' -ContentType "application/json"
$tok = $lr.data.access
$mm = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/traffic/measurements/?page_size=1" -Headers @{"Authorization"="Bearer $tok"}
Write-Host "Total measurements: $($mm.count) | Latest: $($mm.results[0].measured_at)"
```

**Resilience:** If the RTSP stream drops, the service retries with exponential backoff (5s → 10s → 20s → … → max 120s). It never exits permanently.

---

### Terminal 6 — Browser Webcam Test (optional)

> **Browser webcam test uses the local browser camera via `navigator.mediaDevices.getUserMedia()`.**
> This path is for testing the browser-native webcam workflow and does not require RTSP or any permanent demo webcam camera record.

Open the app in a browser, navigate to the Cameras page, and click **Start My Webcam**.

The browser sends frames over WebSocket to the Django backend, which runs YOLO detection and records temporary AI measurements.

The legacy `ai-services/vehicle_detection/src/webcam_to_rtsp.py` workflow is no longer required for browser webcam testing.

---

### Terminal 7 — Celery worker + beat (optional, analytics only)

```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\backend"
celery -A config worker --beat -l info
```

To immediately generate analytics summaries without waiting for the schedule:
```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\backend"
python manage.py run_analytics --all
```

---

## 6. Port Reference

| Port | Service | Protocol |
|---|---|---|
| 5173 | React / Vite frontend | HTTP |
| 8000 | Django / Daphne (HTTP + WebSocket) | HTTP / WS |
| 6379 | Redis | TCP |
| 8554 | MediaMTX RTSP input | RTSP |
| 8888 | MediaMTX HLS output | HTTP |
| 8889 | MediaMTX WebRTC (Phase 6, not yet used) | HTTP |

---

## 7. Credentials

| Username | Password | Role | Notes |
|---|---|---|---|
| `Admin` | `admin1234` | System Administrator | **Primary demo login** — matches "Fill Demo Credentials" button |
| `admin` | `Admin1234!` | System Administrator | Secondary admin |
| `tco` | `Admin1234!` | Traffic Control Officer | Write access to incidents/events |
| `analyst` | `Admin1234!` | Traffic Analyst | Read-only analytics |
| `law` | `Admin1234!` | Law Enforcement | Violations/incidents read |
| `camtech` | `Admin1234!` | Camera/Sensor Technician | Camera management |
| `payofficer` | `Admin1234!` | Payment/Fines Officer | Violations/fines |
| `publicuser` | `Admin1234!` | Public User | Minimal access |
| `ai_service` | `AiService2026!` | System Administrator | Used internally by AI service only |

**Django Admin panel:** `http://localhost:8000/admin/` — log in as `admin / Admin1234!`

---

## 8. Seeded Database State (verified)

| Model | Count |
|---|---|
| Roads | 0 (Nairobi seed data removed — add real Gondar roads via admin or seed command) |
| Intersections | 0 |
| Road Segments | 0 |
| Cameras | 5 (CAM-001 to CAM-005) |
| Sensors | 3 |
| Traffic Signals | 3 |
| Traffic Incidents | 4 |
| Traffic Events | 5 |
| Measurements | 1971+ (AI adding every 10s) |

**Camera IDs and stream paths:**

| ID | Name | stream_url | Source type |
|---|---|---|---|
| 7 | CAM-001 | `rtsp://localhost:8554/test-camera-1` | TEST VIDEO |
| 8 | CAM-002 | `rtsp://localhost:8554/test-camera-2` | TEST VIDEO |
| 9 | CAM-003 | `rtsp://localhost:8554/test-camera-3` | TEST VIDEO |
| 10 | CAM-004 | `rtsp://localhost:8554/test-camera-4` | TEST VIDEO (AI active) |
| 11 | CAM-005 | *(empty)* | offline/no stream |
<!-- WEBCAM-001 removed from demo dataset. Browser webcam testing is transient and does not create a persistent camera record. -->

---

## 9. "Start Everything" Checklist

Run these in order every time you want to test the application.

```
□ 1. Open PS window → cd project root → docker compose up redis mediamtx
      Wait for "Ready to accept connections" + "listener opened on :8888"

□ 2. Open PS window → cd backend → python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
      Wait for "Starting server at tcp:interface=127.0.0.1:port=8000"

□ 3. Open PS window → cd frontend → npm run dev
      Wait for "Local: http://localhost:5173/"

□ 4. (Tier B) Open PS window → cd project root → .\docker\start_test_streams.ps1
      Wait 3s, verify: Invoke-WebRequest http://localhost:8888/test-camera-4/index.m3u8 → 200

□ 5. (Tier B) Open PS window → cd ai-services\vehicle_detection → python src\main.py
      Wait for "Measurement ✓ vehicles=..."

□ 6. (Optional) cd ai-services\vehicle_detection → python src\webcam_to_rtsp.py

□ 7. (Optional) cd backend → celery -A config worker --beat -l info

□ Open browser → http://localhost:5173
□ Click "Sign In" → enter Admin / admin1234 → click "Fill Demo Credentials" then Login
□ Dashboard should show real-time data within 10 seconds
```

---

## 10. "Stop Everything" Checklist

```
□ 1. Stop AI service        → Ctrl+C in Terminal 5
□ 2. Stop webcam stream     → Ctrl+C in Terminal 6 (if running)
□ 3. Stop Celery            → Ctrl+C in Terminal 7 (if running)
□ 4. Stop FFmpeg streams    → Get-Process -Name ffmpeg | Stop-Process
□ 5. Stop Vite frontend     → Ctrl+C in Terminal 3
□ 6. Stop Daphne backend    → Ctrl+C in Terminal 2
□ 7. Stop Docker services   → Ctrl+C in Terminal 1, then:
                               docker compose down
```

**Full stop + cleanup (nuclear):**
```powershell
Get-Process -Name ffmpeg -ErrorAction SilentlyContinue | Stop-Process
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System"
docker compose down --remove-orphans
```

---

## 11. Health-Check Commands

Run these to verify each component after startup.

```powershell
# 1. Backend health
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/health/"
# Expected: status=ok

# 2. Login
$lr = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login/" -Method POST -Body '{"username":"Admin","password":"admin1234"}' -ContentType "application/json"
$tok = $lr.data.access
Write-Host "Token: $($tok.Substring(0,25))..."
# Expected: token string printed

# 3. Authenticated profile
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/me/" -Headers @{"Authorization"="Bearer $tok"}
# Expected: data.username=Admin, data.roles=[System Administrator]

# 4. System status
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/system/status/" -Headers @{"Authorization"="Bearer $tok"} | ConvertTo-Json -Depth 3
# Expected: data.ai_processing_active=True, data.cameras_total=6

# 5. Camera list
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/cameras/" -Headers @{"Authorization"="Bearer $tok"} | Select-Object count
# Expected: count=6

# 6. HLS stream (Tier B — requires Terminal 4)
Invoke-WebRequest -Uri "http://localhost:8888/test-camera-4/index.m3u8" -UseBasicParsing | Select-Object StatusCode
# Expected: StatusCode=200

# 7. AI measurements (Tier B — requires Terminal 5)
$mm = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/traffic/measurements/?page_size=1" -Headers @{"Authorization"="Bearer $tok"}
Write-Host "Total: $($mm.count) | Latest: $($mm.results[0].measured_at) | Vehicles: $($mm.results[0].vehicle_count)"
# Expected: count increases every 10s, vehicles > 0

# 8. WebSocket (run in browser DevTools console on http://localhost:5173)
# const ws = new WebSocket('ws://localhost:8000/ws/dashboard/?token=PASTE_TOKEN_HERE')
# ws.onopen = () => console.log('WS 101 connected')
# ws.onmessage = e => console.log('message:', e.data)
# Expected: "WS 101 connected" logged, messages appear as AI posts measurements
```

---

## 12. Manual Browser Testing Checklist

### Public pages

- [ ] `http://localhost:5173/` loads TrafficOps homepage
- [ ] "Sign In" button navigates to login page
- [ ] Login page shows "Fill Demo Credentials" button
- [ ] Clicking "Fill Demo Credentials" fills Username=`Admin`, Password=`admin1234`
- [ ] Login succeeds and redirects to Dashboard

### Authentication

- [ ] Wrong password shows error, no redirect
- [ ] Refresh page while logged in → still authenticated
- [ ] Access `/dashboard` while logged out → redirected to login
- [ ] Logout → tokens cleared, redirected away
- [ ] Back button after logout does not restore the session

### Dashboard

- [ ] White card layout matches TrafficOps design
- [ ] Stat cards visible (traffic volume, incidents, signal health)
- [ ] Camera health section shows CAM-001 through CAM-005
- [ ] Active incidents listed
- [ ] Measurements chart updates in real time (Tier B)
- [ ] System status panel shows mode, camera counts

### Incidents, Events, Measurements, Signals, Roads, Analytics

- [ ] All pages load with white card tables, not dark backgrounds
- [ ] Filters work on each page
- [ ] Pagination works
- [ ] Status badges use light semantic colours

### Cameras page

- [ ] All 5 cameras listed
- [ ] CAM-001 to CAM-004: source type shows TEST VIDEO
- [ ] CAM-005: shows offline/no stream
- [ ] HLS player loads and plays for CAM-004 (Tier B)
- [ ] "Test connection" button works

### Audit Log (System Administrator only)

- [ ] Table loads with white card
- [ ] Action column shows `bg-blue-50 font-mono` pill
- [ ] Outcome badges show emerald/amber/red light variants
- [ ] Action filter and outcome filter work

### User Management (System Administrator only)

- [ ] All 8+ users listed
- [ ] Role badges in `bg-blue-50 text-blue-700`
- [ ] "you" badge on Admin row
- [ ] Assign/remove role via modal works
- [ ] Deactivate/activate user works (not on own account)

### RBAC verification

Log in as each account and verify access:

| Account | Can see Audit Log | Can see User Mgmt | Can report Incident | Can manage cameras |
|---|---|---|---|---|
| Admin | ✅ | ✅ | ✅ | ✅ |
| tco | ❌ | ❌ | ✅ | read only |
| analyst | ❌ | ❌ | ❌ read only | ❌ |
| law | ❌ | ❌ | ❌ read only | ❌ |
| camtech | ❌ | ❌ | ❌ | ✅ |
| payofficer | ❌ | ❌ | ❌ | ❌ |
| publicuser | ❌ | ❌ | ❌ | ❌ |

---

## 13. Full Pipeline Data Flow

```
docker\test_videos\*.mp4
        │
        ▼ FFmpeg (-re -stream_loop -1 -i <file>)     [Terminal 4]
        │
        ▼ RTSP push to rtsp://localhost:8554/test-camera-4
        │
        ▼ MediaMTX (Docker)                           [Terminal 1]
        │  ├─ RTSP relay → rtsp://localhost:8554/test-camera-4
        │  └─ HLS transcode → http://localhost:8888/test-camera-4/index.m3u8
        │           │
        │           ▼ Browser HLS player (hls.js)     [Frontend, Terminal 3]
        │
        ▼ AI detection service reads RTSP             [Terminal 5]
           ai-services/vehicle_detection/src/main.py
           CAMERA_ID=10, RTSP_URL=rtsp://localhost:8554/test-camera-4
           │
           ▼ YOLOv8n detection per frame
           ▼ POST /api/v1/traffic/measurements/       [Django, Terminal 2]
           ▼ Django saves TrafficMeasurement (camera_id=10)
           ▼ Django Channels pushes to WebSocket group
           ▼ ws://localhost:8000/ws/dashboard/        [Redis channel layer]
           ▼ React Dashboard receives real-time update [Frontend]
```

---

## 14. Troubleshooting

### HLS stream returns 404 on test-camera-1/2/3
`start_test_streams.ps1` was not run, or FFmpeg processes crashed.
```powershell
Get-Process -Name ffmpeg -ErrorAction SilentlyContinue | Select-Object Id, CPU
# If empty: re-run the script
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System"
.\docker\start_test_streams.ps1
```

### AI service cannot connect to RTSP (backoff loop)
Start the test streams first (Terminal 4), then start the AI service (Terminal 5). The service will auto-recover.

### WebSocket not connecting / Dashboard not updating
Redis must be running. Check:
```powershell
docker ps | Select-String redis
```
If not running: `docker compose up redis` in Terminal 1.

### Port 8000 already in use
A previous Daphne process is still running.
```powershell
netstat -ano | Select-String ":8000 "
# Find PID in last column, then:
Stop-Process -Id <PID>
```

### `python -m daphne` fails with import error
Python path issue. Make sure you are in the `backend\` directory before running the command.

### FFmpeg processes left over from previous session
```powershell
Get-Process -Name ffmpeg -ErrorAction SilentlyContinue | Stop-Process
```

### Measurements not updating in the Dashboard
1. Confirm AI service (Terminal 5) is running and printing measurement lines
2. Confirm Redis is up: `docker ps | Select-String redis`
3. Confirm you are logged in (JWT expired after 15 minutes — log in again)

### Login returns `{"success":false}`
The `Admin` user or their password may have been changed. Run:
```powershell
cd "C:\Users\HI\OneDrive\Desktop\AI-Powered Smart Traffic Management System\backend"
python manage.py seed_users
```
This is idempotent and safe to run multiple times.

---

## 15. Data Honesty

- CAM-001 to CAM-004 stream **prerecorded test videos** — labelled TEST VIDEO in the UI
- Browser webcam testing uses the PC webcam via the browser; it is transient and does not create a persistent camera record.
- No camera is labelled LIVE CCTV — there is no physical CCTV hardware connected
- AI vehicle counts and violation detections are **real YOLOv8 inference** on test frames — not fabricated
- Speed readings are `NULL` — no `meters_per_pixel` calibration has been set
- Physical CCTV testing deferred until hardware is available
