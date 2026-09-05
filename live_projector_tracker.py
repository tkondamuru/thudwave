"""
Interactive Whiteboard Ball Tracker (macOS & Continuity Camera Edition)
Optimized for:
1. iPhone Continuity Camera over wireless Apple ecosystem.
2. Auto-detection of camera index (probes iPhone / Mac cameras automatically).
3. Real-time ArUco perspective homography (TL: 3, TR: 2, BR: 1, BL: 0).
4. Dual Mode: Rich console feedback ("Ready to throw ball!") + optional GUI preview.
"""

import cv2
import numpy as np
import urllib.request
import urllib.parse
import time
import sys
import os
import argparse

from hsv_detector import GreenBallDetector
from kalman_tracker import BallKalmanTracker
from aruco_detector import ArUcoTagDetector

SERVER_URL = "http://localhost:8000/hit"
STATUS_URL = "http://localhost:8000/tracker_status"

def send_hit_to_projector(nx, ny, hit_num):
    """Sends normalized hit coordinate [0.0 to 1.0] to the local projector server."""
    try:
        url = f"{SERVER_URL}?x={nx:.3f}&y={ny:.3f}&num={hit_num}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=0.2):
            pass
    except Exception:
        pass

def send_tracker_status(msg, state="INFO", markers=None):
    """Broadcasts camera lock status and ArUco markers to the web canvas."""
    try:
        m_str = ",".join(str(m) for m in (markers or []))
        params = urllib.parse.urlencode({
            "msg": msg,
            "state": state,
            "markers": m_str
        })
        url = f"{STATUS_URL}?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=0.2):
            pass
    except Exception:
        pass

def auto_detect_camera():
    """
    On macOS:
    - Index 0 is the Mac Built-in FaceTime HD Camera.
    - Index 1 is the iPhone Continuity Camera (when connected/active).
    Probes available cameras and picks the active one.
    """
    print("[Camera] Auto-detecting camera...")
    for idx in [0, 1, 2]:
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.release()
                    label = "Mac Built-in Camera" if idx == 0 else "iPhone / External Camera"
                    print(f"  [OK] Connected to Camera [{idx}] ({label})\n")
                    return idx
                cap.release()
        except Exception:
            pass
    print("  Defaulting to Camera [0]\n")
    return 0

def run_mac_tracker(camera_index=None, show_gui=True, rotation=0):
    if camera_index is None:
        camera_index = auto_detect_camera()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ Error: Could not open camera at index {camera_index}.")
        print("Tips for macOS Continuity Camera:")
        print(" 1. Make sure iPhone and Mac have Wi-Fi and Bluetooth turned ON.")
        print(" 2. Make sure both devices are signed in with the same Apple ID.")
        print(" 3. Alternatively, plug iPhone into Mac with a Lightning / USB-C cable.")
        return

    # Try setting HD 720p / 30fps
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    detector = GreenBallDetector()
    tracker = BallKalmanTracker()
    aruco = ArUcoTagDetector()

    board_tags = {}
    board_locked = False
    board_min_x, board_max_x = 0, 1000
    board_min_y, board_max_y = 0, 1000
    board_w = 1000
    board_h = 1000

    flight_history = []
    cooldown_frames = 0
    hit_counter = 0
    tags = {}
    current_detected = set()
    last_detected_markers = set()
    last_console_msg = ""
    last_status_broadcast_time = 0.0

    print("=" * 60)
    print(" 🎯 LIVE PROJECTOR TRACKER ACTIVE (macOS)")
    print("=" * 60)
    print(" • Web Projector: Keep http://localhost:8000 open on projector screen")
    print(" • Aim your iPhone so the 4 whiteboard corner tags are visible:")
    print("   [3] Top-Left  |  [2] Top-Right  |  [1] Bottom-Right  |  [0] Bottom-Left")
    if show_gui:
        print(" • Preview Window: Press [Q] to quit, [R] to rotate 90°")
    else:
        print(" • Running in pure console mode. Press [Ctrl+C] to quit")
    print("=" * 60 + "\n")

    send_tracker_status("Camera Tracker Online: Searching for Whiteboard Markers...", state="START")

    frame_idx = 0
    fps_start_time = time.time()
    fps_display = 30.0
    gui_available = show_gui
    window_name = "Whiteboard Tracking Preview (Q to quit, R to rotate)"

    if gui_available:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        except Exception:
            gui_available = False
            print("ℹ️ OpenCV GUI window not available. Continuing in console-only mode.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            # Apply orientation rotation if needed
            if rotation == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            elif rotation == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif rotation == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            h, w = frame.shape[:2]
            frame_idx += 1

            if frame_idx % 15 == 0:
                elapsed = time.time() - fps_start_time
                fps_display = 15.0 / elapsed if elapsed > 0 else 30.0
                fps_start_time = time.time()

            # 1. ArUco Marker Detection (Frequent when searching, throttled when locked)
            need_aruco = (frame_idx == 1) or (not board_locked and frame_idx % 2 == 0) or (board_locked and frame_idx % 25 == 0)
            if need_aruco:
                new_tags = aruco.detect(frame)
                if new_tags is not None:
                    tags = new_tags
                    frame_tags = {m_id: (int(info['center'][0]), int(info['center'][1]))
                                  for m_id, info in tags.items() if m_id in [0, 1, 2, 3]}
                    current_detected = set(frame_tags.keys())

                    if len(current_detected) == 4:
                        board_tags = frame_tags.copy()
                        if not board_locked:
                            board_locked = True
                            console_msg = "🎯 [ARUCO: 4/4 LOCKED] Whiteboard boundary locked! READY TO THROW BALL!"
                            if console_msg != last_console_msg:
                                print(f"\n{console_msg}\n")
                                last_console_msg = console_msg
                    elif not board_locked:
                        for tid, pt in frame_tags.items():
                            board_tags[tid] = pt

                        # Print console status update
                        tag_names = {3: "TL(3)", 2: "TR(2)", 1: "BR(1)", 0: "BL(0)"}
                        found_names = [tag_names[k] for k in current_detected]
                        console_msg = f"[ArUco: {len(current_detected)}/4] Found: {', '.join(found_names) if found_names else 'None'} | Point camera at whiteboard corners..."
                        if console_msg != last_console_msg and frame_idx % 10 == 0:
                            print(f"\r{console_msg}", end="", flush=True)
                            last_console_msg = console_msg

            # Broadcast tracker status updates to projector browser
            now = time.time()
            if (current_detected != last_detected_markers) or (now - last_status_broadcast_time > 4.0 and len(current_detected) > 0):
                last_detected_markers = set(current_detected)
                last_status_broadcast_time = now
                if board_locked and len(current_detected) == 4:
                    send_tracker_status("4/4 ArUco Markers Locked! Perspective Homography Active.", state="LOCKED", markers=list(current_detected))
                elif len(current_detected) > 0:
                    send_tracker_status(f"Found {len(current_detected)}/4 ArUco Markers on Whiteboard...", state="LOCKING", markers=list(current_detected))

            # Update whiteboard boundaries once locked
            if board_locked and len(board_tags) == 4:
                xs = [p[0] for p in board_tags.values() if p]
                ys = [p[1] for p in board_tags.values() if p]
                board_min_x, board_max_x = min(xs), max(xs)
                board_min_y, board_max_y = min(ys), max(ys)
                board_w = max(1, board_max_x - board_min_x)
                board_h = max(1, board_max_y - board_min_y)

            # 2. Ball Detection & Rebound Physics (Active once whiteboard is locked)
            meas = None
            state = None
            if board_locked:
                ball, _ = detector.detect(frame)
                meas = ball['center'] if ball else None
                state = tracker.update(meas)

                if cooldown_frames > 0:
                    cooldown_frames -= 1

                if meas is not None:
                    mx, my = meas
                    flight_history.append((frame_idx, mx, my))
                    if len(flight_history) > 10:
                        flight_history.pop(0)

                    # Rebound trajectory calculation
                    if len(flight_history) >= 4 and cooldown_frames == 0:
                        for idx in [-2, -3]:
                            if abs(idx) >= len(flight_history):
                                continue
                            fp, xp, yp = flight_history[idx]
                            if (board_min_x - 30 <= xp <= board_max_x + 30) and (board_min_y - 30 <= yp <= board_max_y + 30):
                                f_before, x_before, y_before = flight_history[0]
                                f_after, x_after, y_after = flight_history[-1]
                                v_in = np.hypot(xp - x_before, yp - y_before)
                                v_out = np.hypot(x_after - xp, y_after - yp)

                                # Require real thrown ball speed (v >= 25 px/frame), rejects static noise
                                if v_in >= 25.0 and v_out >= 15.0:
                                    hit_counter += 1
                                    cooldown_frames = 20
                                    flight_history.clear()

                                    # Perspective Homography to Normalized [0.0 - 1.0] Whiteboard Canvas
                                    src_pts = np.float32([board_tags[3], board_tags[2], board_tags[1], board_tags[0]])
                                    dst_pts = np.float32([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
                                    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
                                    pt = np.array([[[xp, yp]]], dtype=np.float32)
                                    trans = cv2.perspectiveTransform(pt, H)[0, 0]
                                    nx = max(0.0, min(1.0, float(trans[0])))
                                    ny = max(0.0, min(1.0, float(trans[1])))

                                    print(f"\n💥 [IMPACT #{hit_counter}] Rebound at X={nx:.3f}, Y={ny:.3f} (Speed={v_in:.0f}px/f) -> Broadcasted to Projector!")
                                    send_hit_to_projector(nx, ny, hit_counter)
                                    break
                else:
                    if len(flight_history) > 0 and (frame_idx - flight_history[-1][0] > 6):
                        flight_history.clear()

            # 3. Optional GUI Window Rendering (if available)
            if gui_available:
                try:
                    # Draw Whiteboard boundary quad if locked
                    if board_locked and len(board_tags) == 4:
                        poly = np.array([board_tags[3], board_tags[2], board_tags[1], board_tags[0]], dtype=np.int32)
                        cv2.polylines(frame, [poly], True, (0, 255, 128), 2)
                        cv2.putText(frame, "TARGET WHITEBOARD (READY TO THROW BALL)",
                                    (board_tags[3][0], max(20, board_tags[3][1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1, cv2.LINE_AA)

                    # Draw detected ArUco markers
                    for m_id, info in tags.items():
                        if m_id in [0, 1, 2, 3]:
                            cx, cy = int(info['center'][0]), int(info['center'][1])
                            cv2.circle(frame, (cx, cy), 6, (0, 255, 128), -1)
                            tag_name = {3: "TL(3)", 2: "TR(2)", 1: "BR(1)", 0: "BL(0)"}.get(m_id, str(m_id))
                            cv2.putText(frame, tag_name, (cx - 15, cy - 12),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 128), 1, cv2.LINE_AA)

                    # Draw tracked ball
                    if state is not None:
                        bx, by, _, _ = state
                        cv2.circle(frame, (int(bx), int(by)), 12, (0, 255, 0), 2)

                    # Top HUD bar
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (0, 0), (w, 50), (15, 15, 20), -1)
                    cv2.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)

                    if board_locked:
                        st_text = "ARUCO: 4/4 LOCKED ✓ (READY TO THROW BALL!)"
                        st_col = (0, 255, 128)
                    else:
                        st_text = f"ARUCO: {len(current_detected)}/4 (AIM AT WHITEBOARD CORNERS)"
                        st_col = (0, 220, 255) if len(current_detected) > 0 else (80, 80, 255)

                    cv2.putText(frame, st_text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, st_col, 2, cv2.LINE_AA)
                    metrics = f"{w}x{h} | {fps_display:.0f}FPS | Hits: {hit_counter} | [Q] Quit"
                    cv2.putText(frame, metrics, (max(12, w - 380), 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

                    cv2.imshow(window_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord('q'), ord('Q')]:
                        break
                    elif key in [ord('r'), ord('R')]:
                        rotation = (rotation + 90) % 360
                        print(f"\n  [Orientation] Frame rotated to {rotation}°")
                except Exception:
                    gui_available = False
                    print("\n[Notice] GUI preview unavailable. Switched to console mode.")

    except KeyboardInterrupt:
        print("\nStopping tracker...")
    finally:
        cap.release()
        if gui_available:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        print("Tracker stopped cleanly.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Interactive Projector Whiteboard Tracker for macOS")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (default: auto-detect iPhone Continuity Camera)")
    parser.add_argument("--no-gui", action="store_true", help="Run in pure console mode without preview window")
    parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="Rotate frame (degrees)")
    args = parser.parse_args()

    run_mac_tracker(camera_index=args.camera, show_gui=not args.no_gui, rotation=args.rotate)
