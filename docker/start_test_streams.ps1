
# start_test_streams.ps1
# Starts 4 FFmpeg RTSP streams from prerecorded traffic videos into MediaMTX.
# EXPLICITLY LABELLED: TEST/PRERECORDED sources - NOT LIVE CCTV.
# Data from YOLO processing these streams is REAL AI inference, not fabricated.

$ffmpeg = "C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
$videoDir = "$PSScriptRoot\test_videos"

$streams = @(
    @{ video="27260-362770008_medium.mp4";              path="test-camera-1"; note="Urban intersection 1280x720 30fps, 5 vehicles/frame detected" },
    @{ video="8355-208052034_medium.mp4";               path="test-camera-2"; note="Highway+truck 1280x720 30fps, truck conf=0.90 + cars" },
    @{ video="istockphoto-476627368-mp4-480x480-is.mp4";path="test-camera-3"; note="Dense traffic 480x270 24fps, 15 vehicles/frame BEST COUNTER" },
    @{ video="istockphoto-851692014-640_adpp_is.mp4";   path="test-camera-4"; note="Busy road 768x432 30fps, 39 vehicles/frame BEST TRACKING" }
)

Write-Host "=== TEST RTSP STREAMS (PRERECORDED, NOT LIVE CCTV) ==="
Write-Host "MediaMTX must be running on localhost:8554"
Write-Host ""

foreach ($s in $streams) {
    $videoPath = "$videoDir\$($s.video)"
    $rtspUrl   = "rtsp://localhost:8554/$($s.path)"
    Write-Host "Stream: $($s.path) | $($s.note)"
    Write-Host "  RTSP: $rtspUrl"
    Write-Host "  HLS:  http://localhost:8888/$($s.path)/index.m3u8"
    Start-Process -FilePath $ffmpeg -ArgumentList @(
        "-re", "-stream_loop", "-1", "-i", $videoPath,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-b:v", "800k", "-maxrate", "800k", "-bufsize", "1600k",
        "-f", "rtsp", "-rtsp_transport", "tcp", $rtspUrl
    ) -WindowStyle Hidden
    Start-Sleep -Milliseconds 800
}

Write-Host ""
Write-Host "All 4 test streams started."
