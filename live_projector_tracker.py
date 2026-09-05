"""
Interactive Whiteboard Ball Tracker
Features:
- Pure manual lock: NEVER auto-locks.
- Continuously identifies ArUco markers (0/4, 1/4, 2/4, 3/4, 4/4).
- Press [L] or [l] (in OpenCV window or Terminal) to LOCK when 4/4 are identified.
- Press [L] or [l] to UNLOCK anytime to re-scan.
- When locked: pauses ArUco scanning (zero jitter) and activates ball rebound tracking.
- Sends hit events to http://127.0.0.1:8000/hit.
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

SERVER_URL = "http://127.0.0.1:8000/hit"
STATUS_URL = "http://127.0.0.1:8000/tracker_status"

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

def order_points(pts):
    """
    Orders 4 spatial points in consistent clockwise order:
    [0]: Top-Left, [1]: Top-Right, [2]: Bottom-Right, [3]: Bottom-Left
    Does NOT depend on ArUco tag IDs. Works regardless of tag sticker placement!
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # Top-Left: smallest (x + y)
    rect[2] = pts[np.argmax(s)]      # Bottom-Right: largest (x + y)

    diff = np.diff(pts, axis=1)      # y - x
    rect[1] = pts[np.argmin(diff)]   # Top-Right: smallest (y - x) == largest (x - y)
    rect[3] = pts[np.argmax(diff)]   # Bottom-Left: largest (y - x) == smallest (x - y)
    return rect

def auto_detect_camera():
    """Probes available cameras and picks an active one."""
    print("[Camera] Auto-detecting camera...")
    for idx in [0, 1, 2]:
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.release()
                    label = "Built-in Camera" if idx == 0 else "External / iPhone Camera"
                    print(f"  [OK] Connected to Camera [{idx}] ({label})\n")
                    return idx
                cap.release()
        except Exception:
            pass
    print("  Defaulting to Camera [0]\n")
    return 0

def run_tracker(camera_index=None, show_gui=True, rotation=0, record_file=None):
    if camera_index is None:
        camera_index = auto_detect_camera()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ Error: Could not open camera at index {camera_index}.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 60)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    detector = GreenBallDetector()
    tracker = BallKalmanTracker()
    aruco = ArUcoTagDetector()

    # Whiteboard Corner Map & Lock State (NEVER AUTO-LOCKS)
    board_tags = {}
    is_locked = False
    locked_board_tags = None
    H_matrix = None

    board_min_x, board_max_x = 0, 1000
    board_min_y, board_max_y = 0, 1000
    board_quad = None

    flight_history = []
    ball_trail = []
    active_splash = None
    video_writer = None
    show_mask = False
    cooldown_frames = 0
    hit_counter = 0
    quit_requested = False

    def toggle_lock():
        nonlocal is_locked, locked_board_tags, H_matrix, board_quad
        nonlocal board_min_x, board_max_x, board_min_y, board_max_y

        if not is_locked:
            # Check if all 4 corners (TL:3, TR:2, BR:1, BL:0) are identified
            missing_ids = [m for m in [3, 2, 1, 0] if m not in board_tags]
            if not missing_ids:
                # All 4 corners present! Lock them
                is_locked = True
                locked_board_tags = {k: board_tags[k] for k in [0, 1, 2, 3]}

                # Automatically sort 4 physical points into: TL, TR, BR, BL
                raw_pts = np.array([locked_board_tags[k] for k in [0, 1, 2, 3]], dtype=np.float32)
                ordered_pts = order_points(raw_pts)
                board_quad = ordered_pts

                xs = ordered_pts[:, 0]
                ys = ordered_pts[:, 1]
                board_min_x, board_max_x = float(np.min(xs)), float(np.max(xs))
                board_min_y, board_max_y = float(np.min(ys)), float(np.max(ys))

                src_pts = ordered_pts
                dst_pts = np.float32([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
                H_matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

                send_tracker_status([0, 1, 2, 3], is_locked=True)

                print("\n" + "=" * 65)
                print(" 🔒 [LOCKED] 4 Whiteboard Corners FROZEN in place!")
                print("   • Sent lock update to browser! (Whiteboard LOCKED)")
                print(f"   • Top-Left:     ({int(ordered_pts[0][0])}, {int(ordered_pts[0][1])})")
                print(f"   • Top-Right:    ({int(ordered_pts[1][0])}, {int(ordered_pts[1][1])})")
                print(f"   • Bottom-Right: ({int(ordered_pts[2][0])}, {int(ordered_pts[2][1])})")
                print(f"   • Bottom-Left:  ({int(ordered_pts[3][0])}, {int(ordered_pts[3][1])})")
                print("   • ArUco scanning is PAUSED (Zero jitter).")
                print("   • Directional ball rebound tracking is ACTIVE!")
                print("   • Press [L] again to unlock if you move the camera/laptop.")
                print("=" * 65 + "\n")
            else:
                missing_names = [f"Tag {m}" for m in missing_ids]
                found_count = 4 - len(missing_ids)

                print("\n" + "!" * 65)
                print(f" ⚠️ [CANNOT LOCK] Only {found_count}/4 corners identified!")
                print(f"   Missing: {', '.join(missing_names)}")
                print("   Camera must see all 4 corners before locking.")
                print("   (Did not send any update to browser)")
                print("!" * 65 + "\n")
        else:
            # Unlock corners
            is_locked = False
            locked_board_tags = None
            H_matrix = None
            board_quad = None
            send_tracker_status([], is_locked=False)

            print("\n" + "=" * 65)
            print(" 🔓 [UNLOCKED] Whiteboard corners unlocked!")
            print("   • Sent unlock update to browser.")
            print("   • Live ArUco scanning resumed.")
            print("   • Reposition camera as needed.")
            print("   • Press [L] when all 4 corners are visible to re-lock.")
            print("=" * 65 + "\n")

    # Terminal keyboard listener thread
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
    print(" 🎯 LIVE PROJECTOR TRACKER ACTIVE")
    print("=" * 65)
    print(" • Web Projector: http://localhost:8000")
    print(" • Markers: [3] Top-Left | [2] Top-Right | [1] Bottom-Right | [0] Bottom-Left")
    print(" • NO AUTO-LOCK: Press [L] or [l] to Lock/Unlock (in Window or Terminal)")
    print(" • Press [Q] to Quit, [R] to Rotate Preview")
    print("=" * 65 + "\n")

    frame_idx = 0
    fps_start_time = time.time()
    fps_display = 60.0
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

            if record_file and video_writer is None:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                rec_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                if rec_fps < 10 or rec_fps > 120:
                    rec_fps = 30.0
                video_writer = cv2.VideoWriter(record_file, fourcc, rec_fps, (w, h))
                print(f"\n🎥 [Recording] Output video will be saved to: {record_file} ({rec_fps:.0f} FPS)\n")

            if frame_idx % 30 == 0:
                elapsed = time.time() - fps_start_time
                fps_display = 30.0 / elapsed if elapsed > 0 else 60.0
                fps_start_time = time.time()

            # 1. ArUco Marker Scanning
            # When LOCKED: Paused completely (0 jitter, 0 readjustment, 0 CPU)
            # When UNLOCKED: Scans every 2 frames, NEVER AUTO-LOCKS
            if not is_locked:
                if (frame_idx == 1) or (frame_idx % 2 == 0):
                    tags = aruco.detect(frame)
                    if tags:
                        for m_id, info in tags.items():
                            if m_id in [0, 1, 2, 3]:
                                board_tags[m_id] = (int(info['center'][0]), int(info['center'][1]))

                # Print progress to terminal only (ZERO updates sent to browser until [L] is pressed)
                now = time.time()
                current_keys = tuple(sorted(board_tags.keys()))
                if (current_keys != last_broadcast_keys) or (now - last_broadcast_time > 1.0):
                    last_broadcast_keys = current_keys
                    last_broadcast_time = now

                    found_names = [f"Tag {k}" for k in sorted(board_tags.keys())]
                    if len(board_tags) == 4:
                        status_str = "🎯 [4/4 IDENTIFIED] All 4 corners in view! Press [L] on terminal to lock."
                    else:
                        status_str = f"📷 [{len(board_tags)}/4 Identified] Found: {', '.join(found_names) if found_names else 'Searching...'}"
                    print(f"\r{status_str}", end="", flush=True)

            # 2. Ball Detection & Rebound Physics (Active when manually locked)
            meas = None
            state = None
            mask = None
            if is_locked and H_matrix is not None:
                ball, mask = detector.detect(frame)
                meas = ball['center'] if ball else None
                state = tracker.update(meas)

                if cooldown_frames > 0:
                    cooldown_frames -= 1
                    # During cooldown: keep all buffers clean so floor rebound doesn't pollute next throw
                    flight_history.clear()
                    ball_trail.clear()
                    tracker.reset()
                    detector.reset()
                elif meas is not None:
                    mx, my = meas
                    flight_history.append((frame_idx, mx, my))
                    ball_trail.append((int(mx), int(my)))
                    if len(flight_history) > 30:
                        flight_history.pop(0)
                    if len(ball_trail) > 35:
                        ball_trail.pop(0)

                    # Directional Rebound trajectory calculation
                    if len(flight_history) >= 6 and board_quad is not None:
                        for idx in [-2, -3, -4]:
                            if abs(idx) >= len(flight_history):
                                continue
                            fp, xp, yp = flight_history[idx]

                            # 1. Whiteboard Quad Boundary Check: reject points outside the physical whiteboard
                            dist = cv2.pointPolygonTest(board_quad, (float(xp), float(yp)), True)
                            if dist < -15.0:
                                continue

                            # 2. Directional Vectors: approach vector vs rebound vector
                            idx_before = max(0, len(flight_history) + idx - 5)
                            f_before, x_before, y_before = flight_history[idx_before]
                            f_after, x_after, y_after = flight_history[-1]

                            dx_in = xp - x_before
                            dy_in = yp - y_before
                            v_in = float(np.hypot(dx_in, dy_in))

                            dx_out = x_after - xp
                            dy_out = y_after - yp
                            v_out = float(np.hypot(dx_out, dy_out))

                            # Must have significant motion approaching and rebounding
                            if v_in >= 15.0 and v_out >= 10.0:
                                dot = (dx_in * dx_out) + (dy_in * dy_out)
                                cos_angle = dot / (v_in * v_out)

                                # In free flight: cos_angle >= 0.70 (straight continuous arc).
                                # In a physical rebound: cos_angle <= 0.35 (trajectory bends sharply or reverses).
                                if cos_angle <= 0.35:
                                    hit_counter += 1
                                    cooldown_frames = 25
                                    flight_history.clear()
                                    ball_trail.clear()
                                    tracker.reset()
                                    detector.reset()

                                    # Perspective transform using FROZEN H_matrix
                                    pt = np.array([[[xp, yp]]], dtype=np.float32)
                                    trans = cv2.perspectiveTransform(pt, H_matrix)[0, 0]
                                    raw_nx, raw_ny = float(trans[0]), float(trans[1])
                                    nx = max(0.0, min(1.0, raw_nx))
                                    ny = max(0.0, min(1.0, raw_ny))

                                    active_splash = {'pt': (int(xp), int(yp)), 'nx': nx, 'ny': ny, 'frames': 45}
                                    angle_deg = float(np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0))))

                                    print(f"\n💥 [IMPACT #{hit_counter}] Rebound Deflection={angle_deg:.1f}° (cos={cos_angle:.2f})")
                                    print(f"   • Impact Pixel:       ({xp:.0f}, {yp:.0f})")
                                    print(f"   • Transform Output:   Raw X={raw_nx:.3f}, Raw Y={raw_ny:.3f}")
                                    print(f"   • Normalized Sent:    X={nx:.3f}, Y={ny:.3f} -> Projector Server")
                                    print(f"   • Approach / Rebound: in={v_in:.0f}px, out={v_out:.0f}px\n")
                                    send_hit_to_projector(nx, ny, hit_counter)
                                    break
                else:
                    # When ball is absent for > 15 frames (e.g. retrieving ball from floor), clear buffers
                    if len(flight_history) > 0 and (frame_idx - flight_history[-1][0] > 15):
                        flight_history.clear()
                        tracker.reset()
                        ball_trail.clear()
                    elif len(ball_trail) > 0:
                        ball_trail.pop(0)

            # 3. Visual Annotations (Trail, Splash, Markers, Quad)
            active_tags = locked_board_tags if is_locked else board_tags

            # Draw boundary quad
            if len(active_tags) == 4 and all(k in active_tags for k in [0, 1, 2, 3]):
                pts = np.array([active_tags[k] for k in [0, 1, 2, 3]], dtype=np.float32)
                ordered = order_points(pts).astype(np.int32)
                poly = ordered.reshape((-1, 1, 2))
                border_color = (0, 255, 128) if is_locked else (0, 220, 255)
                cv2.polylines(frame, [poly], True, border_color, 2)
                label = "🔒 LOCKED (READY TO THROW BALL)" if is_locked else "4/4 IDENTIFIED - PRESS [L] TO LOCK"
                cv2.putText(frame, label,
                            (int(ordered[0][0]), max(20, int(ordered[0][1]) - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, border_color, 1, cv2.LINE_AA)

            # Draw markers
            for m_id, pt in active_tags.items():
                cx, cy = int(pt[0]), int(pt[1])
                pt_color = (0, 255, 128) if is_locked else (0, 220, 255)
                cv2.circle(frame, (cx, cy), 6, pt_color, -1)
                cv2.putText(frame, f"Tag {m_id}", (cx - 15, cy - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, pt_color, 1, cv2.LINE_AA)

            if is_locked:
                # Draw ball motion trail (yellow fading line)
                for i in range(1, len(ball_trail)):
                    thick = max(1, int(i / 6))
                    cv2.line(frame, ball_trail[i - 1], ball_trail[i], (0, 255, 255), thick)

                # Draw impact splash (expanding red bullseye)
                if active_splash and active_splash['frames'] > 0:
                    s_pt = active_splash['pt']
                    radius = max(6, (46 - active_splash['frames']) * 2)
                    cv2.circle(frame, s_pt, radius, (0, 0, 255), 3)
                    cv2.circle(frame, s_pt, 4, (0, 0, 255), -1)
                    cv2.putText(frame, f"HIT! Cam:{s_pt} -> ({active_splash['nx']:.2f}, {active_splash['ny']:.2f})",
                                (max(10, s_pt[0] - 100), max(30, s_pt[1] - 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2, cv2.LINE_AA)
                    active_splash['frames'] -= 1

            # Draw tracked ball
            if state is not None:
                bx, by, _, _ = state
                cv2.circle(frame, (int(bx), int(by)), 12, (0, 255, 0), 2)
                if meas is not None:
                    cv2.circle(frame, (int(meas[0]), int(meas[1])), 4, (0, 255, 0), -1)

            # Picture-in-Picture mask preview when [M] is toggled
            if show_mask and mask is not None:
                mask_thumb = cv2.resize(mask, (240, 135))
                mask_bgr = cv2.cvtColor(mask_thumb, cv2.COLOR_GRAY2BGR)
                frame[h - 145:h - 10, w - 250:w - 10] = mask_bgr
                cv2.rectangle(frame, (w - 250, h - 145), (w - 10, h - 10), (0, 255, 255), 1)
                cv2.putText(frame, "COLOR MASK [M]", (w - 245, h - 130), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            # Top HUD bar
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 52), (15, 15, 20), -1)
            cv2.addWeighted(overlay, 0.85, frame, 0.15, 0, frame)

            if is_locked:
                st_text = "🔒 LOCKED (PRESS [L] TO UNLOCK)"
                st_col = (0, 255, 128)
            elif len(board_tags) == 4:
                st_text = "🎯 4/4 IDENTIFIED: PRESS [L] TO LOCK"
                st_col = (0, 255, 255)
            else:
                st_text = f"SEARCHING: {len(board_tags)}/4 IDENTIFIED (PRESS [L] WHEN 4/4)"
                st_col = (0, 200, 255) if len(board_tags) > 0 else (80, 80, 255)

            rec_indicator = " [REC 🔴]" if video_writer else ""
            cv2.putText(frame, st_text + rec_indicator, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, st_col, 2, cv2.LINE_AA)
            metrics = f"{w}x{h} | {fps_display:.0f}FPS | Hits: {hit_counter} | [L] Lock | [M] Mask | [Q] Quit"
            cv2.putText(frame, metrics, (max(12, w - 460), 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

            # Write frame to video if recording
            if video_writer is not None:
                video_writer.write(frame)

            # 4. OpenCV GUI Window Rendering
            if gui_available:
                try:
                    cv2.imshow(window_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord('q'), ord('Q')]:
                        break
                    elif key in [ord('l'), ord('L')]:
                        toggle_lock()
                    elif key in [ord('m'), ord('M')]:
                        show_mask = not show_mask
                        print(f"  [Debug] Mask preview: {'ON' if show_mask else 'OFF'}")
                    elif key in [ord('r'), ord('R')]:
                        rotation = (rotation + 90) % 360
                        print(f"\n  [Orientation] Frame rotated to {rotation}°")
                except Exception:
                    gui_available = False

    except KeyboardInterrupt:
        print("\nStopping tracker...")
    finally:
        cap.release()
        if video_writer is not None:
            video_writer.release()
            print(f"🎬 Video recording saved successfully to: {record_file}")
        if gui_available:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        print("Tracker stopped cleanly.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Interactive Projector Whiteboard Tracker")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (default: auto-detect)")
    parser.add_argument("--no-gui", action="store_true", help="Pure console mode without preview window")
    parser.add_argument("--rotate", type=int, default=0, choices=[0, 90, 180, 270], help="Rotate frame (degrees)")
    parser.add_argument("--record", type=str, default=None, help="Save annotated tracking video to MP4 file")
    parser.add_argument("--output", type=str, default=None, help="Alias for --record")
    args = parser.parse_args()

    record_target = args.record or args.output
    run_tracker(camera_index=args.camera, show_gui=not args.no_gui, rotation=args.rotate, record_file=record_target)
