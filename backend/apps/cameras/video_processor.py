"""
Video processing worker: reads uploaded video, runs VehicleDetector per frame,
draws annotations, encodes annotated video, and writes JSON/CSV summary.

This is designed to run in a background thread or worker process.
"""
import os
import json
import csv
import math
import logging
import platform
import shutil
import subprocess
from datetime import datetime

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Use the centralized loader to avoid duplicate loading logic
from apps.cameras.detector_loader import get_vehicle_detector
from apps.cameras.pipeline import analyze_frame


def _reencode_browser_compatible_mp4(source_path: str) -> str:
    """Re-encode the finished MP4 into a Chromium-friendly H.264/AAC-like MP4 profile.

    The analysis pipeline still writes the annotated frames and keeps the same output path,
    but the final artifact is re-encoded with libx264 and yuv420p to avoid the unsupported
    mp4v/mpeg4 output that Chromium reports as DEMUXER_ERROR_NO_SUPPORTED_STREAMS.
    """
    if not source_path or not os.path.exists(source_path):
        return source_path

    ffmpeg_bin = shutil.which('ffmpeg')
    if not ffmpeg_bin:
        logger.warning('ffmpeg not found; leaving generated annotated video as-is.')
        return source_path

    tmp_path = f'{source_path}.tmp_h264.mp4'
    cmd = [
        ffmpeg_bin,
        '-y',
        '-hide_banner',
        '-loglevel', 'error',
        '-i', source_path,
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-profile:v', 'high',
        '-level', '4.0',
        '-movflags', '+faststart',
        '-an',
        tmp_path,
    ]

    try:
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            logger.warning('H.264 re-encode failed for %s: %s', source_path, completed.stderr.strip() or completed.stdout.strip() or 'unknown ffmpeg error')
            return source_path
        if os.path.exists(tmp_path):
            os.replace(tmp_path, source_path)
        return source_path
    except Exception as exc:
        logger.warning('H.264 re-encode exception for %s: %s', source_path, exc)
        return source_path


def _try_ocr_crop(pil_img):
    # Placeholder OCR function — return None unless pytesseract is available
    try:
        import pytesseract
        text = pytesseract.image_to_string(pil_img)
        return text.strip() or None
    except Exception:
        return None


def process_video_job(job, meters_per_pixel: float | None = None):
    """Process a TemporaryVideoAnalysis job instance in-place.

    job: TemporaryVideoAnalysis model instance (unsaved or saved) with .upload file
    meters_per_pixel: optional float to enable speed estimation
    """
    from apps.cameras.models import TemporaryVideoAnalysis
    try:
        job.result_json = {'stage': 'loading_model', 'progress': 1}
        job.save(update_fields=['result_json'])
        detector = None
        try:
            detector = get_vehicle_detector(conf_threshold=0.35)
        except Exception as exc:
            # Let the outer exception handler capture and persist the traceback
            raise

        infile = job.upload.path
        cap = cv2.VideoCapture(infile)
        if not cap.isOpened():
            job.status = TemporaryVideoAnalysis.STATUS_FAILED
            job.result_json = {'error': 'Could not open uploaded video'}
            job.save(update_fields=['status', 'result_json'])
            return

        job.result_json = {'stage': 'extracting_frames', 'progress': 5}
        job.save(update_fields=['result_json'])

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Prepare output annotated video path
        out_dir = os.path.join(os.path.dirname(job.upload.path), 'annotated')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'annotated_{job.pk}.mp4')

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

        # Per-track last position for speed compute
        last_pos = {}
        last_time = {}
        per_frame_events = []
        frames_output = []

        processed = 0
        job.status = TemporaryVideoAnalysis.STATUS_PROCESSING
        start_time = datetime.utcnow()
        job.result_json = {'stage': 'running_detection', 'progress': 10}
        job.save(update_fields=['status', 'result_json'])

        tracks = {}
        violations = []
        snapshot_dir = os.path.join(out_dir, 'snapshots')
        os.makedirs(snapshot_dir, exist_ok=True)

        def _make_snapshot(image, filename):
            path = os.path.join(snapshot_dir, filename)
            cv2.imwrite(path, image)
            return path

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx = processed
            timestamp = frame_idx / (fps or 25.0)

            detections = detector.detect(frame)

            # Use shared pipeline to analyze frame
            state = {
                'last_pos': last_pos,
                'last_time': last_time,
                'tracks': tracks,
                'violations': violations,
            }
            frame_dets, new_events, annotated_frame, state = analyze_frame(detections, frame, timestamp, meters_per_pixel, state)

            # restore state references
            last_pos = state.get('last_pos', {})
            last_time = state.get('last_time', {})
            tracks = state.get('tracks', {})
            violations = state.get('violations', [])

            # Save thumbnails for newly observed tracks if possible
            for det in frame_dets:
                tid = str(det.get('track_id'))
                track = tracks.get(tid)
                if track and track.get('thumbnail') is None:
                    try:
                        bbox = track.get('bboxes', [])[-1]
                        x1 = int(bbox[0] * w)
                        y1 = int(bbox[1] * h)
                        x2 = int(bbox[2] * w)
                        y2 = int(bbox[3] * h)
                        crop = annotated_frame[y1:y2, x1:x2]
                        if crop.size > 0:
                            thumb_path = _make_snapshot(crop, f'track_{tid}_first.jpg')
                            tracks[tid]['thumbnail'] = thumb_path
                    except Exception:
                        pass

            frames_output.append({'time': timestamp, 'detections': frame_dets})

            writer.write(annotated_frame)

            # progress update every few frames
            processed += 1
            if frame_count > 0 and processed % 10 == 0:
                pct = int(processed / max(1, frame_count) * 100)
                job.result_json = {'stage': 'running_detection', 'progress': pct}
                job.save(update_fields=['result_json'])

        # Finalize
        cap.release()
        writer.release()
        _reencode_browser_compatible_mp4(out_path)

        # Build summary
        counts = {}
        plates = set()
        for f in frames_output:
            for d in f['detections']:
                counts[d['class']] = counts.get(d['class'], 0) + 1
                if d.get('plate'):
                    plates.add(d['plate'])

        summary = {
            'processed_frames': processed,
            'fps': fps,
            'resolution': f'{w}x{h}',
            'events': per_frame_events,
            'vehicle_counts': counts,
            'plates': list(plates),
            'violations': violations,
            'generated_at': datetime.utcnow().isoformat() + 'Z',
        }

        # CSV
        csv_path = os.path.join(out_dir, f'results_{job.pk}.csv')
        with open(csv_path, 'w', newline='', encoding='utf8') as fh:
            writer_csv = csv.writer(fh)
            writer_csv.writerow(['time_s', 'event_type', 'track_id', 'plate'])
            for ev in per_frame_events:
                writer_csv.writerow([ev.get('time'), ev.get('type'), ev.get('track_id'), ev.get('plate')])

        # Build track summaries
        for track in tracks.values():
            track['duration_seconds'] = track['last_seen'] - track['first_seen']
            if track['speed_history']:
                track['avg_speed'] = sum(track['speed_history']) / len(track['speed_history'])
            else:
                track['avg_speed'] = None
            if track['thumbnail']:
                track['thumbnail'] = os.path.join(os.path.dirname(job.upload.name), 'annotated', 'snapshots', os.path.basename(track['thumbnail']))

        snapshot_list = []
        for track_id, track in tracks.items():
            if track.get('thumbnail'):
                snapshot_list.append({
                    'type': 'first_detection',
                    'track_id': track_id,
                    'time': track['first_seen'],
                    'image': track['thumbnail'],
                })
        for v in violations:
            snapshot_list.append({
                'type': 'violation',
                'track_id': v['track_id'],
                'time': v['time'],
                'speed_kmh': v['speed_kmh'],
            })

        # Full JSON results file (frames + summary)
        results_obj = {
            'summary': summary,
            'frames': frames_output,
            'vehicles': list(tracks.values()),
            'violations': violations,
            'snapshots': snapshot_list,
            'ai_metadata': {
                'model_name': 'YOLOv8n',
                'yolov8_version': None,
                'confidence_threshold': 0.35,
                'fps_processed': fps,
                'frames_analyzed': processed,
                'speed_calibrated': meters_per_pixel is not None,
                'ocr_engine': 'pytesseract',
                'cpu_cores': os.cpu_count(),
                'platform': platform.platform(),
                'processing_start': start_time.isoformat() + 'Z',
                'processing_end': datetime.utcnow().isoformat() + 'Z',
            },
        }
        try:
            import ultralytics
            results_obj['ai_metadata']['yolov8_version'] = getattr(ultralytics, '__version__', None)
        except Exception:
            pass

        json_path = os.path.join(out_dir, f'results_{job.pk}.json')
        with open(json_path, 'w', encoding='utf8') as fh:
            json.dump(results_obj, fh, ensure_ascii=False, indent=2)

        # Optionally generate a PDF report (if reportlab is installed)
        pdf_path = None
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            pdf_path = os.path.join(out_dir, f'report_{job.pk}.pdf')
            c = canvas.Canvas(pdf_path, pagesize=letter)
            c.setFont('Helvetica-Bold', 14)
            c.drawString(36, 750, 'Video Analysis Report')
            c.setFont('Helvetica', 10)
            c.drawString(36, 730, f"File: {job.original_filename}")
            c.drawString(36, 716, f"Processed frames: {processed}")
            c.drawString(36, 702, f"FPS: {fps}")
            c.drawString(36, 688, f"Resolution: {w}x{h}")
            y = 660
            c.setFont('Helvetica-Bold', 12)
            c.drawString(36, y, 'Vehicle counts:')
            y -= 16
            c.setFont('Helvetica', 10)
            for cls, cnt in counts.items():
                c.drawString(48, y, f"{cls}: {cnt}")
                y -= 12
                if y < 72:
                    c.showPage()
                    y = 750
            c.save()
        except Exception:
            pdf_path = None

        # Update stage to rendering_overlays
        job.result_json = {'stage': 'rendering_overlays', 'progress': 90}
        job.save(update_fields=['result_json'])

        job.result_json = summary
        # Save annotated video into job.annotated_video (store relative path under upload dir)
        rel_path = os.path.relpath(out_path, os.path.dirname(job.upload.path))
        job.annotated_video.name = os.path.join(os.path.dirname(job.upload.name), 'annotated', os.path.basename(out_path))
        # Attach paths to results (relative to upload dir) so views can serve or read files
        # Save absolute results file paths into result_json for the download view to pick up
        job.result_json['results_file'] = os.path.join(os.path.dirname(job.upload.name), 'annotated', os.path.basename(json_path))
        job.result_json['csv_file'] = os.path.join(os.path.dirname(job.upload.name), 'annotated', os.path.basename(csv_path))
        if pdf_path:
            job.result_json['pdf_file'] = os.path.join(os.path.dirname(job.upload.name), 'annotated', os.path.basename(pdf_path))

        # Final stage updates
        job.result_json = job.result_json or {}
        job.result_json['stage'] = 'complete'
        job.result_json['progress'] = 100
        job.status = TemporaryVideoAnalysis.STATUS_DONE
        job.save(update_fields=['result_json', 'annotated_video', 'status'])

    except Exception as exc:
        # Capture full traceback and failing stage to aid debugging
        import traceback
        tb = traceback.format_exc()
        logger.exception('Video processing failed: %s', exc)
        try:
            job.status = TemporaryVideoAnalysis.STATUS_FAILED
            # Preserve any existing stage info if present
            stage = getattr(job, 'result_json', {}) or {}
            failing_stage = stage.get('stage') if isinstance(stage, dict) else None
            job.result_json = {
                'error': str(exc),
                'traceback': tb,
                'failing_stage': failing_stage or 'unknown',
            }
            job.save(update_fields=['status', 'result_json'])
        except Exception:
            # If saving the job fails, log the traceback to the logger as a last resort
            logger.error('Additionally failed to save job failure state: %s', traceback.format_exc())
