"""
RTSP frame reader with automatic reconnection.

Reads frames from an RTSP stream using OpenCV.
On failure, waits and retries up to MAX_RETRIES times.

NOTE: RTSP credentials are never returned to the browser.
      The full authenticated URL is only used here inside the AI service process.
"""

import logging
import time
import os

import cv2

logger = logging.getLogger(__name__)

MAX_RETRIES    = int(os.getenv("MAX_RECONNECT_ATTEMPTS", "10"))
RETRY_DELAY    = float(os.getenv("RECONNECT_DELAY_SECONDS", "5"))
FRAME_SKIP     = 5   # Process every Nth frame to reduce CPU load on CPU-only inference


class RTSPReader:
    def __init__(self, rtsp_url: str, camera_id: int):
        self.rtsp_url  = rtsp_url
        self.camera_id = camera_id
        self.cap: cv2.VideoCapture | None = None
        self._frame_count = 0

    def _connect(self) -> bool:
        if self.cap:
            self.cap.release()
        logger.info("Connecting to RTSP stream: camera_id=%d", self.camera_id)
        self.cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        if self.cap.isOpened():
            logger.info("RTSP connected: camera_id=%d fps=%.1f",
                        self.camera_id, self.cap.get(cv2.CAP_PROP_FPS))
            return True
        logger.warning("RTSP connection failed: camera_id=%d", self.camera_id)
        return False

    def connect_with_retry(self) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            if self._connect():
                return True
            logger.info("Retry %d/%d in %.0fs…", attempt, MAX_RETRIES, RETRY_DELAY)
            time.sleep(RETRY_DELAY)
        logger.error("Could not connect after %d attempts: camera_id=%d", MAX_RETRIES, self.camera_id)
        return False

    def read_frame(self):
        """
        Read the next processable frame.
        Returns (frame, frame_number) or (None, -1) on failure.
        Skips FRAME_SKIP-1 frames between processable frames to save CPU.
        """
        if not self.cap or not self.cap.isOpened():
            return None, -1

        # Skip frames to reduce CPU load (grab without decoding)
        for _ in range(FRAME_SKIP - 1):
            self.cap.grab()

        ret, frame = self.cap.read()
        if not ret:
            return None, -1

        self._frame_count += 1
        return frame, self._frame_count

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None
