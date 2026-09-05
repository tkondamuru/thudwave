# 🍎 Interactive Whiteboard Game — macOS & Continuity Camera Guide

Welcome to the **macOS Edition** of Project THUD-WAVE / Arcade Bullseye.  
By using your Mac and iPhone with **Apple Continuity Camera**, you get **60 FPS optical clarity**, **0ms latency**, and **zero corporate IT restrictions**.

---

## 📁 What is in this folder?

```text
mac/
├── web_projector_server.py      # Lean HTTP & SSE game server (hosts HTML5 canvas & audio)
├── live_projector_tracker.py    # Auto-detects iPhone Continuity Camera & tracks ball impacts
├── aruco_detector.py            # High-speed ArUco whiteboard corner tag detector
├── hsv_detector.py              # Tuned ball detector (optimized for neon balls)
├── kalman_tracker.py            # Kalman filter physics trajectory & velocity solver
├── config.py                    # Ball color thresholds and geometry filters
├── projector_calibration.json   # Saves your whiteboard corner pin positions
├── MAC_SETUP_GUIDE.md           # This setup guide
└── web/
    └── index.html               # Fullscreen interactive projector game (WebGL/Canvas + Web Audio)
```

---

## ⚡ Step 1: Transfer the `mac/` Folder to Your Mac

You can copy this `mac/` folder from your Windows laptop to your Mac using any of the following:
* **AirDrop** (fastest if Wi-Fi/Bluetooth is available)
* **USB Flash Drive / External SSD**
* **Google Drive / Dropbox / OneDrive**
* **Git** (`git pull` on your Mac)

---

## 📦 Step 2: One-Time Mac Terminal Setup (30 Seconds)

1. Open the **Terminal** app on your Mac (press `Cmd + Space`, type `Terminal`, and hit `Enter`).
2. Verify Python 3 is installed:
   ```bash
   python3 --version
   ```
   *(Every modern Mac with Xcode comes with Python 3).*
3. Navigate into the `mac` folder (example):
   ```bash
   cd ~/Downloads/mac   # or wherever you copied the folder
   ```
4. Install the two required libraries:
   ```bash
   pip3 install opencv-python numpy
   ```

---

## 📽️ Step 3: Connect Magcubic Projector to Your Mac

1. Plug the projector's HDMI cable into your Mac (use a standard USB-C to HDMI adapter if your Mac only has USB-C ports).
2. On your Mac, open **System Settings $\to$ Displays**:
   * Set the projector to **Extended Display** (not "Mirror").
3. Your Mac's screen remains your primary desktop for Terminal commands, while the projector displays the game canvas.

---

## 📱 Step 4: Position Your iPhone (Apple Continuity Camera)

1. Place your iPhone on a tripod or table pointing at your physical whiteboard.
2. **Make sure**:
   * Wi-Fi and Bluetooth are **ON** on both your Mac and iPhone.
   * Both devices are logged into the same Apple ID.
   * *(Optional)*: Plug your iPhone into your Mac with a Lightning or USB-C cable for 0% battery drain.
3. Apple's macOS will **automatically detect your iPhone as an ultra-high-definition webcam** without installing any third-party apps!

---

## 🚀 Step 5: Launch the System

### Terminal 1: Start the Projector Game Server
In your first Terminal window:
```bash
python3 web_projector_server.py
```
* On your Mac, open **Safari** or **Chrome**.
* Drag the browser window onto the **Magcubic Projector screen**.
* Navigate to: **`http://localhost:8000`**
* Click the green **Fullscreen** button (or press `F11` / `Cmd + Ctrl + F`) to make the canvas fill the projected area.

---

### Terminal 2: Start the Live Camera Tracker
Open a second Terminal tab (`Cmd + T`) and run:
```bash
python3 live_projector_tracker.py
```

The script will automatically probe and connect to your iPhone Continuity Camera:
```text
🔍 Auto-detecting camera (checking iPhone Continuity Camera & Mac)...
  ✓ Connected to Camera [1] (iPhone Continuity Camera)

🎯 LIVE PROJECTOR TRACKER ACTIVE (macOS)
```

#### What you will see in the Terminal:
1. **Searching**:
   ```text
   [ArUco: 1/4] Found: BR(1) | Point camera at whiteboard corners...
   ```
2. **Locked**:
   ```text
   🎯 [ARUCO: 4/4 LOCKED] Whiteboard boundary locked! READY TO THROW BALL!
   ```
3. **When you throw a ball**:
   ```text
   💥 [IMPACT #1] Rebound at X=0.482, Y=0.615 (Speed=42px/f) -> Broadcasted to Projector!
   ```
   At the exact millisecond the ball bounces off the whiteboard, the projector triggers a neon shockwave ring and plays a deep **BOOM!** sound!

---

## 🎯 Step 6: Whiteboard Pin Calibration (How It Works)

* On the projector canvas, press the **`[C]`** key to enter **Calibration Mode**.
* 4 glowing cyan pins will appear on the 4 corners:
  * **Top-Left (TL)**, **Top-Right (TR)**, **Bottom-Right (BR)**, **Bottom-Left (BL)**.
* Drag each pin with your mouse (or select with keys `1`, `2`, `3`, `4` and nudge with Arrow keys) until they align with the physical borders of your whiteboard.
* Press **`[C]`** again to lock.
* **Auto-Save**: Pin positions are automatically saved to `projector_calibration.json` on disk and your browser's local storage. You will never have to recalibrate unless you move the projector!

---

## 💡 Optional Flags for the Tracker

* **Pure Console Mode (No pop-up preview window)**:
  ```bash
  python3 live_projector_tracker.py --no-gui
  ```
* **Specify Camera Index Manually**:
  ```bash
  python3 live_projector_tracker.py --camera 1
  ```
* **Rotate Camera Feed (if mounted upside-down or sideways)**:
  ```bash
  python3 live_projector_tracker.py --rotate 90
  ```
  *(Or simply press **`[R]`** while the preview window is focused)*.
