import cv2
import numpy as np
import os
import sys
import glob
from hsv_detector import GreenBallDetector
from kalman_tracker import BallKalmanTracker
from aruco_detector import ArUcoTagDetector

def detect_whiteboard_hits(video_path, output_dir='output_videos'):
    """
    Detects physical ball impacts on the whiteboard using a single front-facing camera.
    Identifies the exact rebound vertex (where horizontal/vertical flight abruptly reverses).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    out_path = os.path.join(output_dir, f"detected_hits_{base_name}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

    detector = GreenBallDetector()
    tracker = BallKalmanTracker()
    aruco = ArUcoTagDetector()

    # Pre-locked 4 physical corners of the whiteboard
    board_tags = {
        0: (68, 354),   # Bottom-Left
        1: (396, 341),  # Bottom-Right
        2: (396, 97),   # Top-Right
        3: (51, 127)    # Top-Left
    }
    board_min_x, board_max_x = 51, 396
    board_min_y, board_max_y = 97, 354

    # Tracking & Impact State Machine
    recorded_hits = []      # List of (hit_idx, x, y, frame_idx, time_ms)
    flight_history = []     # Consecutive ball measurements during a throw: [(frame, x, y), ...]
    active_splash = None    # Visual splash animation: {'pt': (x, y), 'radius': 10, 'frames_left': 15}
    cooldown_frames = 0     # Cooldown to prevent duplicate hits from the same bounce

    print(f"\nAnalyzing Whiteboard Hits in: {video_path}")
    print(f"  Resolution: {w}x{h} @ {fps:.1f} FPS ({total_frames} frames)")
    print("  Engine: Single-Camera Physical Rebound Detection\n")

    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        current_time_ms = int((frame_idx / fps) * 1000)

        # 1. Whiteboard Canvas Outline
        poly_pts = np.array([board_tags[0], board_tags[1], board_tags[2], board_tags[3]], dtype=np.int32)
        cv2.polylines(frame, [poly_pts], True, (255, 255, 0), 2)
        cv2.putText(frame, "INTERACTIVE WHITEBOARD CANVAS", (board_tags[0][0] + 5, board_tags[0][1] + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 0), 2)

        # 2. Detect Green Ball
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

            # Rebound detection over recent flight trajectory window
            if len(flight_history) >= 3 and cooldown_frames == 0:
                # Inspect recent candidate peak points (accounting for 1-frame physical contact dwell)
                for idx in [-2, -3]:
                    if abs(idx) >= len(flight_history):
                        continue
                    fp, xp, yp = flight_history[idx]
                    
                    # Verify the impact vertex lies inside the physical whiteboard boundary
                    if (board_min_x - 10 <= xp <= board_max_x + 10) and (board_min_y - 10 <= yp <= board_max_y + 10):
                        f_before, x_before, _ = flight_history[0]
                        f_after, x_after, _ = flight_history[-1]
                        
                        dx_approach = xp - x_before   # Positive: moving rightward toward whiteboard
                        dx_rebound = x_after - xp     # Negative: rebounding leftward off whiteboard
                        
                        if dx_approach >= 15.0 and dx_rebound <= -8.0:
                            hit_x, hit_y = int(xp), int(yp)
                            hit_num = len(recorded_hits) + 1
                            hit_time_ms = int((fp / fps) * 1000)
                            recorded_hits.append((hit_num, hit_x, hit_y, fp, hit_time_ms))
                            cooldown_frames = 15  # Debounce to prevent multi-triggering on single rebound
                            flight_history.clear()

                            # Trigger visual splash animation
                            active_splash = {'pt': (hit_x, hit_y), 'radius': 12, 'frames_left': 18, 'num': hit_num}
                            print(f"  [Direct Hit #{hit_num:2d}] Impact at ({hit_x:3d}, {hit_y:3d}) on Frame {fp:4d} ({hit_time_ms}ms)")
                            break
        else:
            # Clear flight history only after prolonged loss of track (> 6 frames)
            if len(flight_history) > 0 and (frame_idx - flight_history[-1][0] > 6):
                flight_history.clear()

        # 3. Draw Ball Position and Trail
        if state is not None:
            bx, by, _, _ = state
            cv2.circle(frame, (int(bx), int(by)), 12, (0, 255, 0), 2)
            cv2.circle(frame, (int(bx), int(by)), 4, (0, 0, 255), -1)

        # 4. Render Persistent Historical Hit Markers on Whiteboard
        for h_num, hx, hy, hf, ht in recorded_hits:
            cv2.circle(frame, (hx, hy), 18, (0, 0, 255), 2)
            cv2.circle(frame, (hx, hy), 6, (0, 0, 255), -1)
            cv2.putText(frame, f"#{h_num}", (hx + 10, hy - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)

        # 5. Render Active Impact Splash Animation
        if active_splash is not None and active_splash['frames_left'] > 0:
            s_pt = active_splash['pt']
            s_rad = active_splash['radius']
            # Expanding shockwave rings
            cv2.circle(frame, s_pt, s_rad, (0, 255, 255), 3)
            cv2.circle(frame, s_pt, int(s_rad * 1.6), (0, 165, 255), 2)
            cv2.putText(frame, f"DIRECT HIT #{active_splash['num']}!", (s_pt[0] - 60, s_pt[1] - s_rad - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
            active_splash['radius'] += 3
            active_splash['frames_left'] -= 1

        # 6. Top HUD Header
        cv2.rectangle(frame, (0, 0), (w, 48), (20, 20, 20), -1)
        hud_text = f"Frame: {frame_idx:4d} | Hits Recorded: {len(recorded_hits)}"
        cv2.putText(frame, hud_text, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        # 7. Bottom Status Badge
        cv2.rectangle(frame, (15, h - 50), (450, h - 12), (20, 20, 20), -1)
        status_text = "ENGINE: SINGLE-CAMERA REBOUND DETECTION"
        cv2.putText(frame, status_text, (22, h - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 128), 1)

        out.write(frame)

    cap.release()
    out.release()

    print("\n=== Impact Detection Summary ===")
    print(f"Total Physical Hits Detected: {len(recorded_hits)}")
    for h_num, hx, hy, hf, ht in recorded_hits:
        print(f"  Hit #{h_num:2d} -> ({hx:3d}, {hy:3d}) at Frame {hf:4d} ({ht}ms)")
    print(f"\nSaved annotated video to: {out_path}")

def main():
    search_dir = '.'
    target_video = None

    if len(sys.argv) > 1:
        target_video = sys.argv[1]
    else:
        # Default to video1-front.mp4 if present
        candidates = ['video1-front.mp4', 'video1_front.mp4', '*front*.mp4']
        for c in candidates:
            matches = glob.glob(c)
            if matches:
                target_video = matches[0]
                break

    if not target_video or not os.path.exists(target_video):
        print(f"Could not find a front-camera video. Usage: python detect_whiteboard_hits.py <front_video_path>")
        return

    detect_whiteboard_hits(target_video)

if __name__ == '__main__':
    main()
