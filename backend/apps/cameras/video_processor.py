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

        # CSV export containing genuine detection and tracking records
        csv_path = os.path.join(out_dir, f'results_{job.pk}.csv')
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

        # Collect distinct plates information for reporting
        plates_info_map = {}
        for f in frames_output:
            for d in f.get('detections', []):
                p = d.get('plate')
                if p and p not in plates_info_map:
                    plates_info_map[p] = {
                        'plate': p,
                        'matched': bool(d.get('vehicle')),
                        'vehicle': d.get('vehicle'),
                        'driver': d.get('driver'),
                    }

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

        # Generate professional PDF report
        pdf_path = None
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors

            pdf_path = os.path.join(out_dir, f'report_{job.pk}.pdf')
            c = canvas.Canvas(pdf_path, pagesize=letter)
            page_w, page_h = letter

            # Primary header banner (Deep Slate)
            c.setFillColor(colors.HexColor("#0f172a"))
            c.rect(0, page_h - 70, page_w, 70, fill=True, stroke=False)

            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, page_h - 38, "TrafficOps — AI Video Analysis Report")
            c.setFont("Helvetica", 9)
            c.drawString(40, page_h - 54, "Intelligent Traffic Management System · Evidence & Analytics Dossier")

            # Section 1: Execution Metadata
            y = page_h - 100
            c.setFillColor(colors.HexColor("#1e293b"))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "1. Analysis & Execution Metadata")

            y -= 18
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#334155"))
            meta_items = [
                f"Job ID: #{job.pk}",
                f"Original Filename: {job.original_filename}",
                f"Processing Status: Complete (done)",
                f"Video Geometry: {w}x{h} @ {fps:.1f} FPS",
                f"Frames Analyzed: {processed}",
                f"Speed Calibration Status: {'Calibrated to camera geometry' if meters_per_pixel else 'Uncalibrated / Unavailable (Physical speeds suppressed)'}",
            ]
            for m_line in meta_items:
                c.drawString(55, y, m_line)
                y -= 14

            # Section 2: Counts and Classification
            y -= 10
            c.setFillColor(colors.HexColor("#1e293b"))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "2. Vehicle Counts & Classification Summary")

            y -= 18
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.HexColor("#0f172a"))
            c.drawString(55, y, f"Unique Tracked Vehicles (multi-frame associations): {len(tracks)}")
            y -= 14
            c.drawString(55, y, f"Cumulative Frame Detections (raw per-frame detections): {sum(counts.values())}")

            y -= 18
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#334155"))
            c.drawString(55, y, "Breakdown by detected class:")
            y -= 14
            for cls_name, cnt in sorted(counts.items()):
                c.drawString(70, y, f"• {cls_name.capitalize()}: {cnt} frame detections")
                y -= 13

            # Section 3: ANPR / Plate Resolution
            y -= 10
            c.setFillColor(colors.HexColor("#1e293b"))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "3. License Plate Recognition & Registry Resolution")

            y -= 18
            if not plates_info_map:
                c.setFont("Helvetica-Oblique", 9)
                c.setFillColor(colors.HexColor("#64748b"))
                c.drawString(55, y, "No license plate candidates extracted from evaluated video frames.")
                y -= 14
            else:
                c.setFont("Helvetica", 9)
                for p_entry in list(plates_info_map.values())[:6]:
                    p_val = p_entry.get('plate', '')
                    m_stat = "[CONFIRMED REGISTRY MATCH]" if p_entry.get('matched') else "[UNREGISTERED / CANDIDATE ONLY]"
                    c.setFillColor(colors.HexColor("#0f172a"))
                    c.drawString(55, y, f"Candidate Plate: {p_val} — {m_stat}")
                    y -= 13
                    c.setFillColor(colors.HexColor("#475569"))
                    if p_entry.get('matched') and p_entry.get('vehicle'):
                        vh = p_entry['vehicle']
                        c.drawString(70, y, f"Vehicle: {vh.get('year', '')} {vh.get('make', '')} {vh.get('model', '')} ({vh.get('color', '')})".strip())
                        y -= 13
                    if p_entry.get('matched') and p_entry.get('driver'):
                        dr = p_entry['driver']
                        c.drawString(70, y, f"Driver: {dr.get('full_name', '')} (License: {dr.get('license_number', '')})")
                        y -= 13
                    if not p_entry.get('matched'):
                        c.drawString(70, y, "No registered vehicle matched this plate in the traffic registry.")
                        y -= 13

            # Section 4: Speed & Compliance Notes
            y -= 10
            c.setFillColor(colors.HexColor("#1e293b"))
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "4. Speed & Traffic Rule Compliance")
            y -= 18
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#334155"))
            if not meters_per_pixel:
                c.drawString(55, y, "Speed Measurements: Unavailable. Accurate physical speed requires camera ground-plane calibration.")
                y -= 14
                c.drawString(55, y, "Speed Violations: None asserted (footage is uncalibrated).")
                y -= 14
            else:
                c.drawString(55, y, "Speed Measurements: Calibrated to scene geometry.")
                y -= 14

            # Footer
            c.setStrokeColor(colors.HexColor("#cbd5e1"))
            c.line(40, 45, page_w - 40, 45)
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.HexColor("#94a3b8"))
            c.drawString(40, 32, "TrafficOps Stage E Evidence Dossier · YOLOv8 Object Detection · DeepSORT Tracking")
            c.drawRightString(page_w - 40, 32, "University Internship Presentation Build")

            c.save()
            logger.info("Generated PDF report at %s", pdf_path)
        except Exception as pdf_err:
            logger.warning("PDF report generation encountered an error: %s", pdf_err)
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
