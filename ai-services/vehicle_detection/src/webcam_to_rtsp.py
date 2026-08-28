"""
webcam_to_rtsp.py — Stream PC webcam to MediaMTX via FFmpeg pipe.

Uses OpenCV to read webcam frames and pipes them to FFmpeg which
pushes RTSP to MediaMTX. This avoids DirectShow device conflicts.

Label: LIVE-WEBCAM (not prerecorded, not synthetic)
"""

import subprocess
import sys
import os
import cv2
import numpy as np

FFMPEG = os.getenv(
    "FFMPEG_PATH",
    r"C:\Users\HI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
)
RTSP_URL   = os.getenv("WEBCAM_RTSP_URL", "rtsp://localhost:8554/live-webcam")
CAMERA_IDX = int(os.getenv("WEBCAM_INDEX", "0"))
WIDTH  = 640
HEIGHT = 480
FPS    = 15


def main():
    cap = cv2.VideoCapture(CAMERA_IDX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    if not cap.isOpened():
        print(f"ERROR: Cannot open webcam index {CAMERA_IDX}", file=sys.stderr)
        sys.exit(1)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Webcam opened: {actual_w}x{actual_h}")
    print(f"Streaming to: {RTSP_URL}")
    print("Source label: LIVE-WEBCAM (PC integrated camera)")

    ffmpeg_cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{actual_w}x{actual_h}",
        "-r", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-b:v", "500k",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        RTSP_URL,
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Webcam read failed, retrying...")
                continue

            try:
                proc.stdin.write(frame.tobytes())
            except BrokenPipeError:
                print("FFmpeg pipe closed, exiting.")
                break

            frame_count += 1
            if frame_count % (FPS * 5) == 0:
                print(f"Streaming: {frame_count} frames → {RTSP_URL}")

    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        cap.release()
        proc.stdin.close()
        proc.wait()


if __name__ == "__main__":
    main()
