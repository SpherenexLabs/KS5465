import os
import time
import threading
import math
import cv2
import numpy as np
from flask import Flask, Response, render_template, request, jsonify, send_from_directory

from detector import VehicleDetector
from firebase_admin_rtdb import (
    init_firebase, write_defaults_if_missing, patch_root, push_log, get_root
)

# -------- Flask setup --------
app = Flask(
    __name__,
    template_folder="../web/templates",
    static_folder="../web/static"
)

# -------- Model path --------
server_dir = os.path.dirname(__file__)
model_candidates = [
    os.path.join(server_dir, "models", "best.pt"),
    os.path.join(server_dir, "model", "best.pt"),
]

MODEL_PATH = next((p for p in model_candidates if os.path.exists(p)), None)
if MODEL_PATH is None:
    raise FileNotFoundError(
        "Put YOLO model at server/models/best.pt (or server/model/best.pt), named best.pt."
    )

detector = VehicleDetector(MODEL_PATH, conf=0.20, imgsz=512)

# -------- Video source --------
def create_placeholder_frame(w=1280, h=720):
    """Create a placeholder frame when camera is unavailable"""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)  # Dark gray background
    
    # Add text
    text1 = "Camera Not Available"
    text2 = "Checking camera permissions..."
    text3 = "System will work once camera is connected"
    
    cv2.putText(frame, text1, (w//2 - 300, h//2 - 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (100, 100, 255), 3)
    cv2.putText(frame, text2, (w//2 - 280, h//2 + 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (150, 150, 150), 2)
    cv2.putText(frame, text3, (w//2 - 380, h//2 + 70), 
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (150, 150, 150), 2)
    
    # Add border
    cv2.rectangle(frame, (20, 20), (w-20, h-20), (100, 100, 255), 3)
    
    return frame

def init_camera():
    """Try to initialize camera with multiple fallbacks"""
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_MSMF, "Media Foundation"),
        (cv2.CAP_ANY, "Auto-detect")
    ]
    
    for idx in [1, 2]:
        for backend, name in backends:
            try:
                print(f"Trying camera {idx} with {name} backend...")
                cap = cv2.VideoCapture(idx, backend)
                
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print(f"✓ SUCCESS: Camera {idx} working with {name}!")
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        return cap
                cap.release()
            except Exception as e:
                print(f"  Failed: {e}")
    
    print("\n" + "="*60)
    print("⚠️  NO CAMERA DETECTED")
    print("="*60)
    print("System will continue running with placeholder video.")
    print("\nTo fix camera:")
    print("  1. Close all apps using camera (Teams, Zoom, Skype)")
    print("  2. Check Windows Settings > Privacy > Camera")
    print("  3. Restart your computer")
    print("  4. Try using phone as webcam (DroidCam/IP Webcam)")
    print("="*60 + "\n")
    return None

cap = init_camera()
placeholder_frame = create_placeholder_frame()
using_placeholder = (cap is None)  # Track if we're using placeholder

frame_lock = threading.Lock()
latest_frame = None

detection_lock = threading.Lock()
latest_detections = []

# Shared state (mirrors Firebase)
state_lock = threading.Lock()
state = {
    "Mode": "A",
    "Line": 1,
    "Signal": "RED",
    "Density": 0,
    "Status": "Normal",
    "GreenTime": 15,
    "TimeLeft": 15,
    "Count": 0,
    "OccPct": 0.0
}

running = True

last_firebase_error = 0.0

def _log_firebase_error(action, exc):
    global last_firebase_error
    now = time.time()
    if now - last_firebase_error >= 5.0:
        print(f"[FIREBASE] {action} failed: {exc}")
        last_firebase_error = now

def safe_get_root(default=None):
    try:
        return get_root()
    except Exception as exc:
        _log_firebase_error("get_root", exc)
        return {} if default is None else default

def safe_patch_root(data):
    try:
        patch_root(data)
        return True
    except Exception as exc:
        _log_firebase_error("patch_root", exc)
        return False

def safe_push_log(data):
    try:
        push_log(data)
        return True
    except Exception as exc:
        _log_firebase_error("push_log", exc)
        return False

# ---------- ROI Lines (4 regions) ----------
def get_rois(w, h):
    # 4 vertical ROIs covering entire width and most of height
    # Adjusted to capture vehicles better based on typical camera angles
    y = 0.10 * h      # Start higher (10% from top instead of 18%)
    hh = 0.85 * h     # Cover more height (85% instead of 68%)
    return [
        {"id": 1, "x": 0.00*w, "y": y, "ww": 0.25*w, "hh": hh},
        {"id": 2, "x": 0.25*w, "y": y, "ww": 0.25*w, "hh": hh},
        {"id": 3, "x": 0.50*w, "y": y, "ww": 0.25*w, "hh": hh},
        {"id": 4, "x": 0.75*w, "y": y, "ww": 0.25*w, "hh": hh},
    ]

def point_in_roi(cx, cy, roi):
    return (cx >= roi["x"] and cx <= roi["x"] + roi["ww"] and
            cy >= roi["y"] and cy <= roi["y"] + roi["hh"])

def rect_intersection_area(x1, y1, x2, y2, roi):
    ix1 = max(float(x1), float(roi["x"]))
    iy1 = max(float(y1), float(roi["y"]))
    ix2 = min(float(x2), float(roi["x"] + roi["ww"]))
    iy2 = min(float(y2), float(roi["y"] + roi["hh"]))
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    return (ix2 - ix1) * (iy2 - iy1)

def detection_vehicle_label(d):
    name = str(d.get("name", "")).strip()
    if name:
        return name.title()

    cls = int(d.get("cls", -1))
    if cls == 2:
        return "Car"
    if cls == 3:
        return "Bike"
    if cls == 5:
        return "Bus"
    if cls == 7:
        return "Truck"
    return "Vehicle"

def clamp(v, a, b):
    return max(a, min(b, v))

def density_from_count_occ_width(count, occpct, lane_width_px):
    # Binary density: 0 = low/no traffic, 1 = high traffic.
    # Uses both vehicle count and occupied area with lane width normalization.
    lane_width_px = max(1.0, float(lane_width_px))
    width_capacity = max(1.0, lane_width_px / 75.0)
    count_ratio = float(count) / width_capacity

    is_high_traffic = (count >= 2) or (count_ratio >= 0.45) or (occpct >= 8.0)
    return 1 if is_high_traffic else 0

def green_time_from_density(d):
    # Base green = 15s, but high traffic (density=1) gets 30s
    if d == 1:
        return 30
    return 15

def density_label(d):
    return "High traffic" if int(d) == 1 else "Low traffic"

def traffic_label_from_count(count):
    c = int(max(0, count))
    if c == 0:
        return "No traffic"
    if c <= 10:
        return "Moderate traffic"
    return "Heavy traffic"

# ---------- Signal scheduling (Auto) ----------
phase = "RED"
phase_end = 0.0
phase_duration = 0
current_green_duration = 15
RED_SECONDS = 15
YELLOW_SECONDS = 5

def schedule_phase(next_phase, seconds):
    global phase, phase_end, phase_duration, current_green_duration
    phase_duration = max(1, int(round(float(seconds))))
    phase = next_phase
    phase_end = time.time() + float(phase_duration)
    if next_phase == "GREEN":
        current_green_duration = phase_duration

def phase_time_left():
    if phase_end <= 0:
        return 0
    return max(0, int(math.ceil(phase_end - time.time())))

def auto_signal_step(density_val):
    global phase, phase_end

    next_green = green_time_from_density(density_val)

    if phase_end == 0:
        schedule_phase("GREEN", next_green)
        return "GREEN", current_green_duration, phase_time_left()

    if time.time() >= phase_end:
        if phase == "GREEN":
            schedule_phase("YELLOW", YELLOW_SECONDS)
        elif phase == "YELLOW":
            schedule_phase("RED", RED_SECONDS)
        else:
            schedule_phase("GREEN", next_green)

    # Keep current phase timing stable until phase boundary.
    return phase, current_green_duration, phase_time_left()

# ---------- Threads ----------
def capture_loop():
    global latest_frame, cap, placeholder_frame, using_placeholder
    retry_count = 0
    
    while running:
        if cap is None:
            # Keep showing placeholder and retry camera every 5 seconds
            with frame_lock:
                latest_frame = placeholder_frame.copy()
            using_placeholder = True
            
            if retry_count % 25 == 0:  # Every 5 seconds (25 * 0.2s)
                print("Retrying camera initialization...")
                cap = init_camera()
                if cap is not None:
                    using_placeholder = False
            retry_count += 1
            time.sleep(0.2)
            continue
        
        ok, frame = cap.read()
        if not ok:
            print("Camera read failed, using placeholder...")
            cap.release()
            cap = None
            using_placeholder = True
            with frame_lock:
                latest_frame = placeholder_frame.copy()
            time.sleep(0.5)
            continue
        
        using_placeholder = False
        with frame_lock:
            latest_frame = frame.copy()
        time.sleep(0.01)

def detection_loop():
    global using_placeholder, latest_detections
    last_log = 0.0

    while running:
        with frame_lock:
            frame = None if latest_frame is None else latest_frame.copy()

        if frame is None:
            time.sleep(0.2)
            continue
        
        # Skip detection if using placeholder
        if using_placeholder:
            time.sleep(0.2)
            with state_lock:
                state.update({
                    "Mode": state.get("Mode", "A"),
                    "Status": "Waiting for camera",
                    "Density": 0,
                    "Count": 0,
                    "OccPct": 0.0
                })
            safe_patch_root({
                "Status": "No traffic",
                "Density": 0,
                "Count": 0,
                "OccPct": 0.0,
                "TrafficLabel": "No traffic"
            })
            with detection_lock:
                latest_detections = []
            continue

        # Read Mode/Line from Firebase so dashboard/ESP controls the active lane.
        fb_pre = safe_get_root({}) or {}
        mode_pre = str(fb_pre.get("Mode", "A")).upper()
        if mode_pre not in ("A", "M"):
            mode_pre = "A"
        line_pre = fb_pre.get("Line", 1)
        try:
            line_pre = int(line_pre)
        except Exception:
            line_pre = 1
        if line_pre not in (1, 2, 3, 4):
            line_pre = 1

        h, w = frame.shape[:2]
        rois = get_rois(w, h)
        dets = detector.detect(frame)
        with detection_lock:
            latest_detections = list(dets)
        
        print(f"[DETECTION] Frame: {w}x{h}, Detected: {len(dets)} vehicles")

        active_roi = next((r for r in rois if int(r["id"]) == line_pre), rois[0])
        active_count = 0
        active_occ = 0.0
        for d in dets:
            x1, y1, x2, y2 = d["xyxy"]
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            area = max(0.0, (x2 - x1) * (y2 - y1))
            overlap = rect_intersection_area(x1, y1, x2, y2, active_roi)
            overlap_ratio = overlap / area if area > 0 else 0.0

            if point_in_roi(cx, cy, active_roi) or overlap_ratio >= 0.20:
                active_count += 1
                active_occ += overlap if overlap > 0 else area

        roi_area = float(active_roi["ww"] * active_roi["hh"])
        active_occpct = (active_occ / roi_area) * 100.0 if roi_area > 0 else 0.0
        occpct = float(round(clamp(active_occpct, 0.0, 100.0), 1))

        line = line_pre
        count = int(active_count)
        density_val = int(density_from_count_occ_width(count, occpct, active_roi["ww"]))
        if count <= 0:
            density_val = 0
            occpct = 0.0
        
        print(f"[RESULT] Lane {line}: Count={count}, Density={density_val}, Occ={occpct}%")

        traffic_label = traffic_label_from_count(count)
        status = traffic_label

        # Read Mode/Line from Firebase (so dashboard/ESP controls lane selection state).
        fb = fb_pre
        mode = str(fb.get("Mode", "A")).upper()
        if mode not in ("A", "M"):
            mode = "A"
        fb_line = fb.get("Line", line)
        try:
            fb_line = int(fb_line)
        except Exception:
            fb_line = line
        if fb_line not in (1, 2, 3, 4):
            fb_line = line
        line = fb_line

        # Always read signal from Firebase (hardware/manual source)
        signal = str(fb.get("Signal", "RED")).upper()
        if signal not in ("RED", "YELLOW", "GREEN"):
            signal = "RED"

        green_time = green_time_from_density(density_val)
        time_left = int(state.get("TimeLeft", 0))

        # Update state + Firebase
        with state_lock:
            state.update({
                "Mode": mode,
                "Line": line,
                "Density": density_val,
                "Status": status,
                "Signal": signal,
                "GreenTime": int(green_time),
                "TimeLeft": int(time_left),
                "Count": count,
                "OccPct": occpct
            })

        root_update = {
            "Mode": mode,
            "Density": density_val,
            "Status": status,
            "Count": count,
            "OccPct": occpct,
            "TrafficLabel": traffic_label
        }
        root_update["Line"] = line
        safe_patch_root(root_update)

        # Push Logs every 2 seconds
        if time.time() - last_log >= 2.0:
            last_log = time.time()
            safe_push_log({
                "Mode": mode,
                "Line": line,
                "Density": density_val,
                "Count": count,
                "OccPct": occpct,
                "Status": status,
                "TrafficLabel": traffic_label
            })

        time.sleep(0.1)

# ---------- Stream endpoint ----------
def mjpeg_stream():
    while True:
        with frame_lock:
            frame = None if latest_frame is None else latest_frame.copy()

        if frame is None:
            time.sleep(0.05)
            continue

        with state_lock:
            s = dict(state)
        with detection_lock:
            dets = list(latest_detections)

        # overlay ROIs
        out = frame.copy()
        
        # Draw detected vehicle bounding boxes FIRST
        for d in dets:
            x1, y1, x2, y2 = [int(v) for v in d["xyxy"]]
            cls = d["cls"]
            conf = d["conf"]
            
            if cls == 2:
                color = (0, 255, 0)  # Green
            elif cls == 3:
                color = (255, 0, 255)  # Magenta
            elif cls == 5:
                color = (0, 165, 255)  # Orange
            elif cls == 7:
                color = (0, 255, 255)  # Yellow
            else:
                color = (255, 255, 255)
            label = detection_vehicle_label(d)
            
            # Draw bounding box
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            # Draw label with confidence
            label_text = f"{label} {conf:.2f}"
            cv2.putText(out, label_text, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # show state text

        cv2.putText(out, f"Mode:{s['Mode']}  Density:{s['Density']}  Signal:{s['Signal']}",
                    (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
        cv2.putText(out, f"Count:{s['Count']}  Occ:{s['OccPct']}%  TimeLeft:{s.get('TimeLeft', 0)}s  {density_label(s['Density'])}",
                    (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.70, (255, 255, 255), 2)

        ok, jpg = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
        if not ok:
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
        time.sleep(0.025)

# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/js/<path:filename>")
def js_files(filename):
    return send_from_directory("../web/js", filename)

@app.route("/video_feed")
def video_feed():
    return Response(mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/latest", methods=["GET"])
def api_latest():
    """Compatibility endpoint for clients polling latest traffic state."""
    with state_lock:
        local_state = dict(state)

    fb = safe_get_root({}) or {}
    if not isinstance(fb, dict):
        fb = {}

    merged = dict(local_state)
    merged.update(fb)

    # Keep a consistent timer key for older/newer dashboard clients.
    seconds_val = fb.get("Seconds", merged.get("TimeLeft", 0))
    try:
        seconds_val = max(0, int(seconds_val))
    except Exception:
        seconds_val = 0
    merged["Seconds"] = seconds_val

    return jsonify(merged)

@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.get_json(force=True) or {}
    m = str(data.get("mode", "")).upper()
    if m not in ("A", "M"):
        return jsonify({"ok": False, "error": "mode must be A or M"}), 400
    if not safe_patch_root({"Mode": m}):
        return jsonify({"ok": False, "error": "Firebase update failed; please retry"}), 503
    return jsonify({"ok": True})

@app.route("/api/force", methods=["POST"])
def api_force():
    data = request.get_json(force=True) or {}
    sig = data.get("signal")
    line = data.get("line")

    upd = {"Mode": "M"}  # forcing implies manual
    if sig:
        sig = str(sig).upper()
        if sig not in ("RED", "YELLOW", "GREEN"):
            return jsonify({"ok": False, "error": "signal invalid"}), 400
        upd["Signal"] = sig

    if line is not None:
        try:
            ln = int(line)
        except:
            return jsonify({"ok": False, "error": "line must be 1..4"}), 400
        if ln not in (1, 2, 3, 4):
            return jsonify({"ok": False, "error": "line must be 1..4"}), 400
        upd["Line"] = ln

    if not safe_patch_root(upd):
        return jsonify({"ok": False, "error": "Firebase update failed; please retry"}), 503
    return jsonify({"ok": True})

def start_threads():
    th1 = threading.Thread(target=capture_loop, daemon=True)
    th2 = threading.Thread(target=detection_loop, daemon=True)
    th1.start()
    th2.start()

if __name__ == "__main__":
    init_firebase()
    try:
        write_defaults_if_missing()
    except Exception as exc:
        _log_firebase_error("write_defaults_if_missing", exc)
    start_threads()
    app.run(host="0.0.0.0", port=5000, threaded=True)
