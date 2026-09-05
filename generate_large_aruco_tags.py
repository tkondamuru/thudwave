"""
Generates large, high-contrast, print-ready ArUco markers for the Whiteboard corners.
Dictionary: DICT_4X4_50
Corner mapping:
  - Tag 3: Top-Left (TL)
  - Tag 2: Top-Right (TR)
  - Tag 1: Bottom-Right (BR)
  - Tag 0: Bottom-Left (BL)

Outputs:
  - tag3_top_left.png
  - tag2_top_right.png
  - tag1_bottom_right.png
  - tag0_bottom_left.png
  - print_markers.html (Printable 4-inch layout ready for Safari/Chrome Cmd+P)
"""

import cv2
import numpy as np
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKERS_DIR = os.path.join(OUTPUT_DIR, "markers")
os.makedirs(MARKERS_DIR, exist_ok=True)

dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

tag_info = [
    (3, "TAG 3 - TOP-LEFT (TL)", "tag3_top_left.png"),
    (2, "TAG 2 - TOP-RIGHT (TR)", "tag2_top_right.png"),
    (1, "TAG 1 - BOTTOM-RIGHT (BR)", "tag1_bottom_right.png"),
    (0, "TAG 0 - BOTTOM-LEFT (BL)", "tag0_bottom_left.png"),
]

# Generate 1200x1200px PNGs with wide quiet white borders
for tid, label, filename in tag_info:
    # 800px marker
    if hasattr(cv2.aruco, 'generateImageMarker'):
        raw_marker = cv2.aruco.generateImageMarker(dictionary, tid, 800)
    else:
        raw_marker = cv2.aruco.drawMarker(dictionary, tid, 800)

    # 1200x1200px white canvas (gives 200px quiet zone on all sides for max contrast)
    canvas = np.ones((1200, 1200), dtype=np.uint8) * 255
    canvas[150:950, 200:1000] = raw_marker

    # Add corner label text
    canvas_bgr = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    cv2.putText(canvas_bgr, label, (220, 1060),
                cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(canvas_bgr, "THUD-WAVE CORNER TARGET", (220, 1110),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (120, 120, 120), 2, cv2.LINE_AA)

    out_path = os.path.join(MARKERS_DIR, filename)
    cv2.imwrite(out_path, canvas_bgr)
    print(f"  [OK] Created: {filename} (4.5-inch high-res printable marker)")

# Generate Printable HTML Sheet (print_markers.html)
# Formatted for standard 8.5" x 11" paper with cut lines
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Printable ArUco Whiteboard Markers (4x4 Inches)</title>
<style>
  @page {
    size: letter;
    margin: 0.4in;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    padding: 0;
    background: #fff;
    color: #000;
  }
  .page {
    page-break-after: always;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-around;
    height: 98vh;
  }
  .page:last-child {
    page-break-after: avoid;
  }
  .marker-card {
    border: 2px dashed #999;
    padding: 16px;
    border-radius: 8px;
    text-align: center;
    width: 4.8in;
    box-sizing: border-box;
  }
  .marker-img {
    width: 3.8in;
    height: 3.8in;
    display: block;
    margin: 0 auto;
  }
  .marker-title {
    font-size: 20px;
    font-weight: bold;
    margin-top: 10px;
    letter-spacing: 1px;
  }
  .marker-sub {
    font-size: 13px;
    color: #555;
    margin-top: 4px;
  }
  .instructions {
    text-align: center;
    padding: 20px;
    border-bottom: 2px solid #ccc;
    margin-bottom: 10px;
  }
  @media print {
    .no-print { display: none; }
  }
</style>
</head>
<body>

<div class="instructions no-print">
  <h2>🎯 Printable Whiteboard Corner Markers (4" x 4")</h2>
  <p>These large 4-inch markers allow your Mac webcam to lock onto the whiteboard from across the room in under 1 second.</p>
  <button onclick="window.print()" style="font-size: 18px; padding: 10px 24px; cursor: pointer; background: #007aff; color: #fff; border: none; border-radius: 8px; font-weight: bold;">
    🖨️ Print Markers (Cmd + P)
  </button>
</div>

<!-- PAGE 1: Top Corners -->
<div class="page">
  <div class="marker-card">
    <img class="marker-img" src="markers/tag3_top_left.png" alt="Tag 3">
    <div class="marker-title">TAG 3 ➔ TOP-LEFT CORNER (TL)</div>
    <div class="marker-sub">Tape to the upper-left corner of your whiteboard</div>
  </div>

  <div class="marker-card">
    <img class="marker-img" src="markers/tag2_top_right.png" alt="Tag 2">
    <div class="marker-title">TAG 2 ➔ TOP-RIGHT CORNER (TR)</div>
    <div class="marker-sub">Tape to the upper-right corner of your whiteboard</div>
  </div>
</div>

<!-- PAGE 2: Bottom Corners -->
<div class="page">
  <div class="marker-card">
    <img class="marker-img" src="markers/tag0_bottom_left.png" alt="Tag 0">
    <div class="marker-title">TAG 0 ➔ BOTTOM-LEFT CORNER (BL)</div>
    <div class="marker-sub">Tape to the lower-left corner of your whiteboard</div>
  </div>

  <div class="marker-card">
    <img class="marker-img" src="markers/tag1_bottom_right.png" alt="Tag 1">
    <div class="marker-title">TAG 1 ➔ BOTTOM-RIGHT CORNER (BR)</div>
    <div class="marker-sub">Tape to the lower-right corner of your whiteboard</div>
  </div>
</div>

</body>
</html>
"""

html_path = os.path.join(OUTPUT_DIR, "print_markers.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n[OK] Successfully generated markers in: {MARKERS_DIR}")
print(f"[OK] Printable HTML sheet saved: {html_path}")
print("   (Open print_markers.html in Safari/Chrome and press Cmd+P to print at exact 4x4 inch size!)")
