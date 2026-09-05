"""
Interactive Whiteboard Ball Tracker (macOS Edition)
1. Auto-detects iPhone Continuity Camera or Mac Built-in Camera.
2. Identifies 4 ArUco corner tags (TL: 3, TR: 2, BR: 1, BL: 0).
3. Manual Lock [L] in OpenCV Window or Terminal:
   - When 4/4 corners are identified, press [L] to freeze them permanently.
   - Pauses ArUco scanning while locked (zero jitter, zero readjustment).
   - Refuses to lock if not all 4 corners are identified.
   - Press [L] again to unlock if laptop/camera position changes.
4. Syncs identified marker state to web projector server.
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

from hsv_detector import GreenBallDetector
from kalman_tracker import BallKalmanTracker
from aruco_detector import ArUcoTagDetector

SERVER_URL = "http://localhost:8000/hit"
STATUS_URL = "http://localhost:8000/tracker_status"
LOCKED_CORNERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locked_whiteboard_corners.json")

def send_hit_to_projector(nx, ny, hit_num):
    """Sends normalized hit coordinate [0.0 to 1.0] asynchronously to projector server."""
    def _send():
        try:
            url = f"{SERVER_URL}?x={nx:.3f}&y={ny:.3f}&num={hit_num}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=0.5):
                pass
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

def send_tracker_status(markers, is_locked):
    """Broadcasts ArUco marker list and lock state asynchronously to web projector."""
    def _send():
        try:
            m_str = ",".join(str(m) for m in (markers or []))
            params = urllib.parse.urlencode({
                "markers": m_str,
                "locked": "1" if is_locked else "0"
            })
            url = f"{STATUS_URL}?{params}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=0.5):
                pass
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()

def auto_detect_camera():
    """
    On macOS:
    - Index 0: Built-in FaceTime HD Camera.
    - Index 1: iPhone Continuity Camera.
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
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    detector = GreenBallDetector()
    tracker = BallKalmanTracker()
    aruco = ArUcoTagDetector()

    # Whiteboard Corner Map & Lock State
    board_tags = {}
    is_locked = False
    locked_board_tags = None
    H_matrix = None

    board_min_x, board_max_x = 0, 1000
    board_min_y, board_max_y = 0, 1000

    flight_history = []
    cooldown_frames = 0
    hit_counter = 0

    quit_requested = False

    def toggle_lock():
        nonlocal is_locked, locked_board_tags, H_matrix
        nonlocal board_min_x, board_max_x, board_min_y, board_max_y

        if not is_locked:
            # Check if all 4 corners (TL:3, TR:2, BR:1, BL:0) are identified
            missing_ids = [m for m in [3, 2, 1, 0] if m not in board_tags]
            if not missing_ids:
                # All 4 corners present! Lock them permanently
                is_locked = True
                locked_board_tags = {k: board_tags[k] for k in [0, 1, 2, 3]}

                xs = [locked_board_tags[k][0] for k in [0, 1, 2, 3]]
                ys = [locked_board_tags[k][1] for k in [0, 1, 2, 3]]
                board_min_x, board_max_x = min(xs), max(xs)
                board_min_y, board_max_y = min(ys), max(ys)

                src_pts = np.float32([locked_board_tags[3], locked_board_tags[2], locked_board_tags[1], locked_board_tags[0]])
                dst_pts = np.float32([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
                H_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

                # Persist to JSON
                try:
                    with open(LOCKED_CORNERS_FILE, 'w', encoding='utf-8') as f:
                        json.dump({str(k): list(v) for k, v in locked_board_tags.items()}, f, indent=2)
                except Exception:
                    pass

                send_tracker_status([0, 1, 2, 3], is_locked=True)

                print("\n" + "=" * 65)
                print(" 🔒 [LOCKED] 4 Whiteboard Corners FROZEN in place!")
                print("=" * 65)
                print(f"   • TL(3): {locked_board_tags[3]}   TR(2): {locked_board_tags[2]}")
                print(f"   • BL(0): {locked_board_tags[0]}   BR(1): {locked_board_tags[1]}")
                print("   • ArUco scanning is PAUSED (Zero jitter, Zero readjustment).")
                print("   • Ball rebound tracking is ACTIVE. Ready to throw ball!")
                print("   • Press [L] again to unlock if you move the camera/laptop.")
                print("=" * 65 + "\n")
            else:
                tag_names = {3: "Top-Left (Tag 3)", 2: "Top-Right (Tag 2)", 1: "Bottom-Right (Tag 1)", 0: "Bottom-Left (Tag 0)"}
                missing_names = [tag_names[m] for m in missing_ids]
                found_count = 4 - len(missing_ids)

                send_tracker_status(list(board_tags.keys()), is_locked=False)

                print("\n" + "!" * 65)
                print(f" ⚠️ [CANNOT LOCK] Only {found_count}/4 corners identified!")
                print(f"   Missing: {', '.join(missing_names)}")
                print("   Camera must see all 4 corners before locking.")
                print("   Adjust camera angle, then press [L] once all 4 are visible.")
                print("!" * 65 + "\n")
        else:
            # Unlock corners
            is_locked = False
            locked_board_tags = None
            H_matrix = None
            send_tracker_status(list(board_tags.keys()), is_locked=False)

            print("\n" + "=" * 65)
            print(" 🔓 [UNLOCKED] Whiteboard corners unlocked!")
            print("=" * 65)
            print("   • Live ArUco scanning resumed.")
            print("   • Reposition camera as needed.")
            print("   • Press [L] when all 4 corners are visible to re-lock.")
            print("=" * 65 + "\n")

    def on_terminal_input():
        nonlocal quit_requested
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if cmd in ['l', 'lock']:
                    toggle_lock()
                elif cmd in ['q', 'quit']:
                    quit_requested = True
                    break
            except Exception:
                break

    term_thread = threading.Thread(target=on_terminal_input, daemon=True)
    term_thread.start()

    print("=" * 65)
    print(" 🎯 LIVE PROJECTOR TRACKER ACTIVE (macOS)")
    print("=" * 65)
    print(" • Web Projector: http://localhost:8000 on projector screen")
    print(" • Markers: [3] Top-Left | [2] Top-Right | [1] Bottom-Right | [0] Bottom-Left")
    print(" • Controls: Press [L] to Lock/Unlock (in Preview Window or Terminal)")
    print("             Press [Q] to Quit, [R] to Rotate Preview")
    print("=" * 65 + "\n")

    # Initial sync to server
    send_tracker_status([], is_locked=False)

    frame_idx = 0
    fps_start_time = time.time()
    fps_display = 30.0
    last_broadcast_time = 0.0
    last_broadcast_keys = None
    gui_available = show_gui
    window_name = "Whiteboard Tracker ([L] Lock/Unlock | [Q] Quit | [R] Rotate)"

    if gui_available:
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        except Exception:
            gui_available = False
            print("ℹ️ OpenCV GUI unavailable. Running in console mode.\n")

    try:
        while not quit_requested:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

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

            # 1. ArUco Marker Scanning
            # When LOCKED: Paused completely (0 jitter, 0 readjustment, 0 CPU)
            # When UNLOCKED: Scans every 2 frames
            if not is_locked:
                if (frame_idx == 1) or (frame_idx % 2 == 0):
                    tags = aruco.detect(frame)
                    if tags:
                        for m_id, info in tags.items():
                            if m_id in [0, 1, 2, 3]:
                                board_tags[m_id] = (int(info['center'][0]), int(info['center'][1]))

                # Broadcast sync to web projector (on change or every 1.5s)
                now = time.time()
                current_keys = tuple(sorted(board_tags.keys()))
                if (current_keys != last_broadcast_keys) or (now - last_broadcast_time > 1.5):
                    last_broadcast_keys = current_keys
                    last_broadcast_time = now
                    send_tracker_status(list(current_keys), is_locked=False)

            # 2. Ball Detection & Rebound Physics (Active when locked)
            meas = None
            state = None
            if is_locked and H_matrix is not None:
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

                                # Require real thrown ball speed (v >= 25 px/frame)
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

            # 3. OpenCV GUI Window Rendering
            if gui_available:
                try:
                    active_tags = locked_board_tags if is_locked else board_tags

                    # Draw boundary quad
                    if len(active_tags) == 4 and all(k in active_tags for k in [0, 1, 2, 3]):
                        poly = np.array([active_tags[3], active_tags[2], active_tags[1], active_tags[0]], dtype=np.int32)
                        border_color = (0, 255, 128) if is_locked else (0, 220, 255)
                        cv2.polylines(frame, [poly], True, border_color, 2)
                        label = "🔒 LOCKED (READY TO THROW BALL)" if is_locked else "4/4 IDENTIFIED - PRESS [L] TO LOCK"
                        cv2.putText(frame, label,
                                    (active_tags[3][0], max(20, active_tags[3][1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, border_color, 1, cv2.LINE_AA)

                    # Draw markers
                    for m_id, pt in active_tags.items():
                        cx, cy = int(pt[0]), int(pt[1])
                        pt_color = (0, 255, 128) if is_locked else (0, 220, 255)
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

                    if is_locked:
                        st_text = "🔒 LOCKED ✓ (PRESS [L] TO UNLOCK)"
                        st_col = (0, 255, 128)
                    elif len(board_tags) == 4:
                        st_text = "🎯 4/4 IDENTIFIED: PRESS [L] TO LOCK"
                        st_col = (0, 255, 255)
                    else:
                        st_text = f"AIM AT CORNERS: {len(board_tags)}/4 IDENTIFIED (PRESS [L] WHEN 4/4)"
                        st_col = (0, 200, 255) if len(board_tags) > 0 else (80, 80, 255)

                    cv2.putText(frame, st_text, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, st_col, 2, cv2.LINE_AA)
                    metrics = f"{w}x{h} | {fps_display:.0f}FPS | Hits: {hit_counter} | [L] Lock | [Q] Quit"
                    cv2.putText(frame, metrics, (max(12, w - 420), 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

                    cv2.imshow(window_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord('q'), ord('Q')]:
                        break
                    elif key in [ord('l'), ord('L')]:
                        toggle_lock()
                    elif key in [ord('r'), ord('R')]:
                        rotation = (rotation + 90) % 360
                        print(f"\n  [Orientation] Frame rotated to {rotation}°")
                except Exception:
                    gui_available = False

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
    parser.add_argument("--camera", type=int, default=None, help="Camera index (default: auto-detect)")
    parser.add_argument("--no-gui", action="store_true", help="Pure console mode without preview window")
    parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="Rotate frame (degrees)")
    args = parser.parse_args()

    run_mac_tracker(camera_index=args.camera, show_gui=not args.no_gui, rotation=args.rotate)
