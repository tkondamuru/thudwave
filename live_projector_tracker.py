"""
Interactive Whiteboard Ball Tracker (macOS & Continuity Camera Edition)
Optimized for:
1. iPhone Continuity Camera over wireless Apple ecosystem or Mac camera.
2. Auto-detection of camera index (probes iPhone / Mac cameras automatically).
3. Real-time ArUco perspective homography (TL: 3, TR: 2, BR: 1, BL: 0).
4. Manual [L] Lock / Freeze Feature:
   - When all 4 corners are identified, press [L] to PERMANENTLY freeze coordinates.
   - Completely pauses ArUco scanning while locked (0 jitter, 0 readjustment, 0 CPU).
   - Rejects lock if not all 4 corners are identified and calls out missing corners.
   - Press [L] again to unlock if laptop or camera position changes.
"""

import cv2
import numpy as np
import urllib.request
import urllib.parse
import time
import sys
import os
import argparse
import json
import threading
import queue

from hsv_detector import GreenBallDetector
from kalman_tracker import BallKalmanTracker
from aruco_detector import ArUcoTagDetector

SERVER_URL = "http://localhost:8000/hit"
STATUS_URL = "http://localhost:8000/tracker_status"
CHECK_LOCK_URL = "http://localhost:8000/check_lock_request"
SET_LOCK_URL = "http://localhost:8000/set_lock_state"

LOCKED_CORNERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locked_whiteboard_corners.json")

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

def check_server_lock_request():
    """Polls projector server to see if user pressed [L] on the browser or server terminal."""
    try:
        req = urllib.request.Request(CHECK_LOCK_URL)
        with urllib.request.urlopen(req, timeout=0.15) as res:
            data = json.loads(res.read().decode('utf-8'))
            return data.get("toggle_requested", False)
    except Exception:
        return False

def notify_server_lock_state(locked, failed=False, msg=""):
    """Notifies the web server of new lock state so it broadcasts SSE to projector."""
    try:
        params = urllib.parse.urlencode({
            "locked": "1" if locked else "0",
            "failed": "1" if failed else "0",
            "msg": msg
        })
        url = f"{SET_LOCK_URL}?{params}"
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

    # Whiteboard Corner Map & Lock State
    board_tags = {}
    is_manually_locked = False
    locked_board_tags = None
    H_matrix = None

    # Load saved corners from previous session if available
    if os.path.exists(LOCKED_CORNERS_FILE):
        try:
            with open(LOCKED_CORNERS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if isinstance(saved, dict) and all(str(k) in saved for k in [0, 1, 2, 3]):
                    board_tags = {int(k): tuple(v) for k, v in saved.items()}
                    print(f"ℹ️ Loaded saved 4 corners from previous session. (Press [L] to lock or adjust)")
        except Exception:
            pass

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

    # Thread-safe queue for keyboard commands from terminal
    console_cmd_queue = queue.Queue()
    stop_console_thread = threading.Event()

    def listen_terminal():
        while not stop_console_thread.is_set():
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if cmd in ['l', 'lock']:
                    console_cmd_queue.put('LOCK_TOGGLE')
                elif cmd in ['q', 'quit']:
                    console_cmd_queue.put('QUIT')
            except Exception:
                break

    term_thread = threading.Thread(target=listen_terminal, daemon=True)
    term_thread.start()

    def toggle_manual_lock():
        nonlocal is_manually_locked, locked_board_tags, H_matrix
        nonlocal board_min_x, board_max_x, board_min_y, board_max_y

        if not is_manually_locked:
            # Check if all 4 required corner tags (3:TL, 2:TR, 1:BR, 0:BL) are present
            missing_ids = [m_id for m_id in [3, 2, 1, 0] if m_id not in board_tags]
            if not missing_ids:
                # All 4 corners identified! Lock them permanently
                is_manually_locked = True
                locked_board_tags = {k: board_tags[k] for k in [0, 1, 2, 3]}

                # Calculate fixed boundaries
                xs = [locked_board_tags[k][0] for k in [0, 1, 2, 3]]
                ys = [locked_board_tags[k][1] for k in [0, 1, 2, 3]]
                board_min_x, board_max_x = min(xs), max(xs)
                board_min_y, board_max_y = min(ys), max(ys)
                board_w = max(1, board_max_x - board_min_x)
                board_h = max(1, board_max_y - board_min_y)

                # Compute fixed perspective homography matrix
                src_pts = np.float32([locked_board_tags[3], locked_board_tags[2], locked_board_tags[1], locked_board_tags[0]])
                dst_pts = np.float32([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
                H_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

                # Save locked corners to disk
                try:
                    with open(LOCKED_CORNERS_FILE, 'w', encoding='utf-8') as f:
                        json.dump({str(k): list(v) for k, v in locked_board_tags.items()}, f, indent=2)
                except Exception:
                    pass

                notify_server_lock_state(True, failed=False, msg="All 4 corners locked")
                send_tracker_status("🔒 4/4 Whiteboard Corners LOCKED! ArUco paused.", state="PERMA_LOCKED", markers=[0, 1, 2, 3])

                print("\n" + "=" * 65)
                print(" 🔒 [PERMANENTLY LOCKED] All 4 Whiteboard corners are frozen!")
                print("=" * 65)
                print(f"   • TL(3): {locked_board_tags[3]}   TR(2): {locked_board_tags[2]}")
                print(f"   • BL(0): {locked_board_tags[0]}   BR(1): {locked_board_tags[1]}")
                print("   • ArUco scanning is PAUSED (Zero jitter, Zero CPU overhead).")
                print("   • Ball rebound tracking is 100% ACTIVE. READY TO PLAY!")
                print("   • Press [L] again to unlock if you move the laptop/camera.")
                print("=" * 65 + "\n")
            else:
                # Missing corners: reject lock and call out which ones are missing
                tag_names = {3: "Top-Left (Tag 3)", 2: "Top-Right (Tag 2)", 1: "Bottom-Right (Tag 1)", 0: "Bottom-Left (Tag 0)"}
                missing_names = [tag_names[m] for m in missing_ids]
                found_count = 4 - len(missing_ids)

                err_msg = f"Cannot Lock: Only {found_count}/4 visible. Missing: {', '.join(missing_names)}"
                notify_server_lock_state(False, failed=True, msg=err_msg)
                send_tracker_status(f"⚠️ Cannot Lock: Only {found_count}/4 visible (Missing: {', '.join(missing_names)})", state="LOCK_FAILED", markers=list(board_tags.keys()))

                print("\n" + "!" * 65)
                print(f" ⚠️ [CANNOT LOCK] Only {found_count}/4 corners identified!")
                print(f"   Missing: {', '.join(missing_names)}")
                print("   The camera must see ALL 4 markers before locking.")
                print("   Adjust camera angle until all 4 markers are detected, then press [L].")
                print("!" * 65 + "\n")
        else:
            # Unlock corners and resume live scanning
            is_manually_locked = False
            locked_board_tags = None
            H_matrix = None
            notify_server_lock_state(False, failed=False, msg="Whiteboard unlocked")
            send_tracker_status("🔓 Whiteboard UNLOCKED. Scanning for ArUco markers...", state="LOCKING", markers=list(board_tags.keys()))

            print("\n" + "=" * 65)
            print(" 🔓 [UNLOCKED] Whiteboard corners unlocked!")
            print("=" * 65)
            print("   • Live ArUco marker scanning resumed.")
            print("   • Reposition laptop or camera as needed.")
            print("   • Press [L] once all 4 corners are visible to freeze them again.")
            print("=" * 65 + "\n")

    print("=" * 65)
    print(" 🎯 LIVE PROJECTOR TRACKER ACTIVE (macOS)")
    print("=" * 65)
    print(" • Web Projector: http://localhost:8000 on projector screen")
    print(" • Aim camera so all 4 ArUco markers are visible:")
    print("   [3] Top-Left  |  [2] Top-Right  |  [1] Bottom-Right  |  [0] Bottom-Left")
    print(" • Press [L] to LOCK all 4 corners once identified (stops jitter completely)")
    print(" • Press [L] again to UNLOCK if laptop/camera is moved")
    if show_gui:
        print(" • Preview Window: [L] Lock/Unlock  |  [R] Rotate  |  [Q] Quit")
    else:
        print(" • Console Mode: Type 'L' + Enter to Lock/Unlock  |  [Ctrl+C] Quit")
    print("=" * 65 + "\n")

    send_tracker_status("Camera Online: Point camera at 4 ArUco markers...", state="START")

    frame_idx = 0
    fps_start_time = time.time()
    fps_display = 30.0
    gui_available = show_gui
    window_name = "Whiteboard Tracking Preview ([L] Lock/Unlock, [Q] Quit, [R] Rotate)"

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

            # Check for console commands
            while not console_cmd_queue.empty():
                cmd = console_cmd_queue.get_nowait()
                if cmd == 'LOCK_TOGGLE':
                    toggle_manual_lock()
                elif cmd == 'QUIT':
                    return

            # Check if user pressed [L] on the browser canvas (polled every 10 frames)
            if frame_idx % 10 == 0:
                if check_server_lock_request():
                    toggle_manual_lock()

            # 1. ArUco Marker Detection
            # When LOCKED: SKIP COMPLETELY (0 jitter, 0 readjustment, 0 CPU)
            # When UNLOCKED: scan every 2 frames
            if not is_manually_locked:
                if (frame_idx == 1) or (frame_idx % 2 == 0):
                    new_tags = aruco.detect(frame)
                    if new_tags is not None:
                        tags = new_tags
                        frame_tags = {m_id: (int(info['center'][0]), int(info['center'][1]))
                                      for m_id, info in tags.items() if m_id in [0, 1, 2, 3]}
                        current_detected = set(frame_tags.keys())

                        for tid, pt in frame_tags.items():
                            board_tags[tid] = pt

                        tag_names = {3: "TL(3)", 2: "TR(2)", 1: "BR(1)", 0: "BL(0)"}
                        found_names = [tag_names[k] for k in sorted(current_detected, reverse=True)]
                        missing_count = 4 - len(board_tags)

                        if len(board_tags) == 4:
                            status_msg = f"🎯 [4/4 IDENTIFIED] Press [L] to LOCK corners and start playing!"
                        else:
                            status_msg = f"[Markers: {len(board_tags)}/4] Identified: {', '.join(found_names) if found_names else 'None'} | Aim at missing {missing_count}..."

                        if status_msg != last_console_msg and frame_idx % 8 == 0:
                            print(f"\r{status_msg}", end="", flush=True)
                            last_console_msg = status_msg

                # Broadcast tracker status updates to projector browser when searching
                now = time.time()
                if (current_detected != last_detected_markers) or (now - last_status_broadcast_time > 3.0 and len(board_tags) > 0):
                    last_detected_markers = set(current_detected)
                    last_status_broadcast_time = now
                    if len(board_tags) == 4:
                        send_tracker_status("4/4 Markers Identified! Press [L] to Lock and Play.", state="ALL_IDENTIFIED", markers=list(board_tags.keys()))
                    else:
                        send_tracker_status(f"Found {len(board_tags)}/4 Markers. Align camera...", state="LOCKING", markers=list(board_tags.keys()))

            # 2. Ball Detection & Rebound Physics (Active once manually locked)
            meas = None
            state = None
            if is_manually_locked and H_matrix is not None:
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

                                    # Perspective transform using FROZEN H_matrix
                                    pt = np.array([[[xp, yp]]], dtype=np.float32)
                                    trans = cv2.perspectiveTransform(pt, H_matrix)[0, 0]
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
                    # Draw Whiteboard boundary quad if locked or identified
                    active_tags = locked_board_tags if is_manually_locked else board_tags
                    if len(active_tags) == 4 and all(k in active_tags for k in [0, 1, 2, 3]):
                        poly = np.array([active_tags[3], active_tags[2], active_tags[1], active_tags[0]], dtype=np.int32)
                        border_color = (0, 255, 128) if is_manually_locked else (0, 220, 255)
                        cv2.polylines(frame, [poly], True, border_color, 2)
                        status_label = "🔒 LOCKED (READY TO THROW BALL)" if is_manually_locked else "4/4 IDENTIFIED - PRESS [L] TO LOCK"
                        cv2.putText(frame, status_label,
                                    (active_tags[3][0], max(20, active_tags[3][1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, border_color, 1, cv2.LINE_AA)

                    # Draw detected or locked ArUco markers
                    draw_tags = locked_board_tags if is_manually_locked else active_tags
                    for m_id, pt in draw_tags.items():
                        cx, cy = int(pt[0]), int(pt[1])
                        pt_color = (0, 255, 128) if is_manually_locked else (0, 220, 255)
                        cv2.circle(frame, (cx, cy), 6, pt_color, -1)
                        tag_name = {3: "TL(3)", 2: "TR(2)", 1: "BR(1)", 0: "BL(0)"}.get(m_id, str(m_id))
                        cv2.putText(frame, tag_name, (cx - 15, cy - 12),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, pt_color, 1, cv2.LINE_AA)

                    # Draw tracked ball
                    if state is not None:
                        bx, by, _, _ = state
                        cv2.circle(frame, (int(bx), int(by)), 12, (0, 255, 0), 2)

                    # Top HUD bar
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (0, 0), (w, 52), (15, 15, 20), -1)
                    cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

                    if is_manually_locked:
                        st_text = "🔒 LOCKED ✓ ARUCO PAUSED (PRESS [L] TO UNLOCK)"
                        st_col = (0, 255, 128)
                    elif len(board_tags) == 4:
                        st_text = "🎯 4/4 IDENTIFIED: PRESS [L] TO LOCK"
                        st_col = (0, 255, 255)
                    else:
                        st_text = f"AIM AT CORNERS: {len(board_tags)}/4 FOUND (PRESS [L] WHEN READY)"
                        st_col = (0, 200, 255) if len(board_tags) > 0 else (80, 80, 255)

                    cv2.putText(frame, st_text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, st_col, 2, cv2.LINE_AA)
                    metrics = f"{w}x{h} | {fps_display:.0f}FPS | Hits: {hit_counter} | [L] Lock | [Q] Quit"
                    cv2.putText(frame, metrics, (max(12, w - 420), 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

                    cv2.imshow(window_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord('q'), ord('Q')]:
                        break
                    elif key in [ord('l'), ord('L')]:
                        toggle_manual_lock()
                    elif key in [ord('r'), ord('R')]:
                        rotation = (rotation + 90) % 360
                        print(f"\n  [Orientation] Frame rotated to {rotation}°")
                except Exception:
                    gui_available = False
                    print("\n[Notice] GUI preview unavailable. Switched to console mode.")

    except KeyboardInterrupt:
        print("\nStopping tracker...")
    finally:
        stop_console_thread.set()
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
