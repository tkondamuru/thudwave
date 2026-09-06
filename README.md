# 🌊 Project THUD-WAVE: Interactive Whiteboard Arcade

Turn any passive whiteboard or wall into an **interactive, impact-sensing gaming surface** using a standard projector, a webcam, and real-time computer vision.

---

## 🎯 Project Goal & Vision

Traditional interactive gaming walls (like Lü Interactive or MultiBall) cost between **$5,000 and $25,000**, requiring proprietary infrared LIDAR bars, specialized touch sensors, and industrial computers.

**Project THUD-WAVE** achieves the same responsive experience using **100% commodity consumer hardware**:
* **Ball Tracking**: High-speed HSV color segmentation, frame differencing, and Kalman velocity estimation tracking fast-moving projectiles at 60 FPS.
* **Wall Impact Point Detection**: Vector kinematics calculating the exact physical rebound vertex ($\cos(\theta) \le -0.42$) to pinpoint the impact pixel on the whiteboard without attaching physical sensors.
* **The "Visual Haptic" Concept**: When a player throws a physical ball against the wall, their hand and ears perceive a physical impact ("thud"). By instantly triggering an explosive kinetic shockwave, particle sparks, and spatial synthesizer audio at the exact coordinate of impact with sub-frame latency, the human brain perceives the wall as a massive digital touch screen.
* **Zero External Server Dependencies**: Built purely on Python 3 Standard Library, OpenCV, and vanilla HTML5 Canvas / Web Audio API.

---

## 📐 System Architecture

```
                                  PHYSICAL ENVIRONMENT
  ┌────────────────────────────────────────────────────────────────────────┐
  │                                                                        │
  │     [Player] ──(Throws Ball)──> [Physical Whiteboard with 4 ArUco Tags]│
  │                                           ▲                            │
  │                                           │ (Projects Visuals)         │
  └───────────────────────────────────────────┼────────────────────────────┘
                                              │
                    ┌─────────────────────────┴────────────────────────────┐
                    │                                                      │
             [Magcubic Projector]                                   [Webcam / iPhone]
                    ▲                                                      │
                    │ (HDMI Display)                                       │ (60 FPS Video)
                    │                                                      ▼
     ┌──────────────┴─────────────────┐                   ┌────────────────┴───────────────┐
     │   HTML5 Canvas Game Engine     │                   │ Python Computer Vision Tracker │
     │       (web/index.html)         │                   │   (live_projector_tracker.py)  │
     │                                │                   │                                │
     │ • Dynamic Bullseye & Rings     │                   │ • Manual [L] ArUco Quad Lock   │
     │ • Kinetic Shockwave Engine     │                   │ • Perspective Transform (H)    │
     │ • Web Audio API Synthesizer    │                   │ • Directional Rebound Physics  │
     │ • Server-Sent Events (SSE)     │                   │ • Kalman Trajectory Predictor  │
     └────────────────▲───────────────┘                   └────────────────┬───────────────┘
                      │                                                    │
                      │             ┌────────────────────────┐             │
                      └─────────────┤ web_projector_server.py├─────────────┘
                        (SSE Stream)│   (Port 8000 / HTTP)   │  (/hit Endpoint)
                                    └────────────────────────┘
```

---

## 📁 Repository Structure

```text
thudwave/
├── web/
│   ├── index.html                   # Arcade Bullseye game (Canvas + Audio + SSE)
│   └── game_template_base.html      # Clean starter template for developing new games
├── web_projector_server.py          # Zero-dependency HTTP & SSE streaming game server
├── live_projector_tracker.py        # Real-time camera tracker (ArUco lock + impact solver)
├── detect_whiteboard_hits.py        # Offline batch video analyzer for test recordings
├── aruco_detector.py                # High-speed ArUco corner tag detection & sorting
├── hsv_detector.py                  # High-saturation color segmenter & motion differencer
├── kalman_tracker.py                # Kalman filter physics velocity & position estimator
├── config.py                        # Ball color thresholds, area, and circularity settings
├── generate_large_aruco_tags.py     # Script to generate printable high-res ArUco markers
├── print_markers.html               # Printable sheet with 4 corner ArUco markers
├── projector_calibration.json       # Persisted 4-pin whiteboard corner calibration
└── markers/                         # Output PNGs of ArUco tags (DICT_4X4_50)
```

---

## 🔬 How It Works (Under the Hood)

### 1. Manual 4-Corner ArUco Alignment (Zero-Jitter Freeze)
* Four ArUco markers (`DICT_4X4_50`, IDs: 3, 2, 1, 0) are placed at the physical corners of the whiteboard:
  * **Tag 3**: Top-Left
  * **Tag 2**: Top-Right
  * **Tag 1**: Bottom-Right
  * **Tag 0**: Bottom-Left
* **Automatic Clockwise Ordering**: Points are spatially sorted using sum ($x+y$) and difference ($y-x$) vectors, independent of sticker rotation.
* **Manual Lock (`[L]` Key)**: The system **never auto-locks**. The user presses `[L]` in the console or camera window once all 4 corners are visible.
* **Zero CPU Jitter**: Once locked, ArUco scanning is 100% halted. The perspective homography matrix ($H$) is frozen, eliminating marker drift.

### 2. Physical Rebound Impact Detection
* Unlike simple frame difference algorithms (which falsely trigger on players' hands or bodies), THUD-WAVE tracks the **vector flight kinematics**:
  $$\vec{v}_{in} = \vec{p}_{impact} - \vec{p}_{approach}$$
  $$\vec{v}_{out} = \vec{p}_{rebound} - \vec{p}_{impact}$$
* When the ball strikes the board, its velocity abruptly reverses. The detector calculates the cosine of the deflection angle:
  $$\cos(\theta) = \frac{\vec{v}_{in} \cdot \vec{v}_{out}}{\|\vec{v}_{in}\| \|\vec{v}_{out}\|}$$
  A true ball rebound produces $\cos(\theta) \le -0.42$ (deflection $> 115^\circ$), strictly rejecting smooth hand-waving motions.
* **Quad Polygon Boundary Clipping**: Rebound candidates outside the physical whiteboard quadrilateral are discarded via `cv2.pointPolygonTest`.
* **Perspective Mapping**: The impact pixel $(x, y)$ is transformed via $H$ into normalized whiteboard space $[0.0, 1.0]$ and transmitted asynchronously to `http://127.0.0.1:8000/hit?x=...&y=...`.

### 3. Dynamic Whiteboard Canvas & Audio Synthesizer
* **Dynamic Bounding Box Fitting**: The browser queries the calibrated 4 pins and calculates the maximum circle that fits inside the whiteboard quad:
  $$r_{max} = \frac{\min(width, height)}{2} \times 0.94$$
  The rings (10 PTS, 25 PTS, 50 PTS, 100 PTS) expand to fill the physical board without leaving awkward empty margins.
* **Zero-Latency Web Audio Synthesizer**: Generates punchy low-frequency sine-wave thumps (160 Hz $\to$ 30 Hz) combined with melodic musical chimes (Web Audio API) without loading external MP3 files.
* **Strict Containment**: Game Over banners, rating badges, and confetti bursts are mathematically clamped to the whiteboard quad, preventing visual overflow onto the wall.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.8+
* Modern Web Browser (Chrome, Safari, or Edge)
* Projector (e.g., Magcubic HY300/HY320 or any standard HDMI projector)
* Webcam (USB webcam, laptop webcam, or iPhone via Apple Continuity Camera)

### 1. Install Dependencies
```bash
cd thudwave
pip install opencv-python numpy
```

### 2. Print Corner Markers
Open `print_markers.html` in your browser and print the sheet:
* Stick **Tag 3** at the Top-Left of your whiteboard.
* Stick **Tag 2** at the Top-Right.
* Stick **Tag 1** at the Bottom-Right.
* Stick **Tag 0** at the Bottom-Left.

*(Or run `python generate_large_aruco_tags.py` to generate custom PNGs).*

### 3. Start the Projector Game Server
In your first terminal:
```bash
python web_projector_server.py
```
* Open **`http://localhost:8000`** in Chrome/Safari.
* Drag the browser window onto the projector display.
* Press **`F11`** (or `Cmd + Ctrl + F` on Mac) for fullscreen.

### 4. Start the Live Ball Tracker
In your second terminal:
```bash
python live_projector_tracker.py
```
* Point the camera at your whiteboard.
* When the terminal shows `🎯 [4/4 IDENTIFIED]`, press **`[L]`** (in the terminal or OpenCV window) to freeze the board corners.
* The browser automatically switches from Calibration Mode to Arcade Game Mode!
* Throw your ball and play!

---

## 🎮 Keyboard & Interactive Controls

| Key | Context | Action |
| :---: | :---: | :--- |
| **`[L]`** | Camera Window / Terminal | **Lock / Unlock** whiteboard ArUco corners |
| **`[R]`** | Tracker Window / Browser | **Reset Round**: reloads 5 throws, clears score, and clears Kalman filters |
| **`[C]`** | Browser Game Canvas | **Toggle Pin Calibration Mode**: drag 4 pins to align projector image with physical whiteboard |
| **`[T]`** | Browser Game Canvas | **Simulate Test Throw**: triggers a random synthetic hit on the bullseye |
| **`[H]`** | Browser Game Canvas | **Toggle HUD**: hides/shows the top navigation bar for a clean arcade look |
| **`[M]`** | Camera Window | **Toggle Mask Preview**: displays the binary HSV color mask for tuning lighting |
| **`[O]`** | Camera Window | **Rotate Preview**: rotates camera feed by 90° increments |
| **`[Q]`** | Camera Window / Terminal | **Quit** the camera tracker |
| **Click & Drag** | Game Mode (Canvas) | Drag the Bullseye target to reposition it anywhere on your whiteboard |

---

## 🧪 Offline Video Analysis (`detect_whiteboard_hits.py`)

If you record a video of ball throws and want to inspect detection accuracy frame-by-frame:
```bash
python detect_whiteboard_hits.py
```
* Processes the video offline, annotates the ball flight trail, draws the rebound deflection vector, and saves an annotated MP4 video with detected hit coordinates.

---

## 🛠️ Calibration & Alignment Tips
1. **Throw Ratio Sweet Spot**: Position the projector so its natural optical beam matches your whiteboard width ($\text{Distance} \approx \text{Width} \times 1.2$). This concentrates all lumens onto the board and maximizes brightness.
2. **Ambient Lighting**: Place a warm lamp or spotlight behind the player aiming toward the flight path. The board remains high-contrast, while the ball stays brightly lit for the camera.
3. **HSV Mask Tuning**: Press **`[M]`** in the tracker window. The ball should show up as a solid white circle against a black background. Adjust `LOWER_ORANGE` in `config.py` if your lighting changes.

---

## 📋 Roadmap & Things to Do (Next Steps)

1. **🏎️ Real-Time Pitch Speedometer (Exit Velocity / Radar Gun)**
   * Convert pixel displacement into real physical units ($v = \Delta d / \Delta t$) using calibrated whiteboard dimensions.
   * Broadcast exit velocity via SSE to display real-time speed metrics (e.g. `"THROW SPEED: 28.5 MPH"`) with fiery visual haptics on high-speed throws.

2. **🛡️ Color-Agnostic Low-Light Tracking (Night & Dark Room Invariance)**
   * Implement adaptive MOG2/KNN background subtraction and high-pass temporal frame differencing across the static whiteboard quad.
   * Eliminate dependence on strict neon HSV thresholds so any projectile (white baseball, gray foam ball, tennis ball) tracks reliably under dim room lighting and projected color changes.

3. **👥 Multi-Ball & Simultaneous Multiplayer Tracking**
   * Multi-color HSV segmentation pipeline (e.g., Player 1 = Orange Ball, Player 2 = Neon Green Ball).
   * Run concurrent Kalman filter state estimators to track dual projectiles in flight simultaneously.
   * Build competitive 2-player split scoring and cooperative arcade battle modes.

