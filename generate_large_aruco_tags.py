"""
Generates large ArUco markers optimized for single-sheet A4 sticker paper (2 columns x 2 rows).
Dictionary: DICT_4X4_50
Corner mapping:
  - Top-Left (TL): Tag 3
  - Top-Right (TR): Tag 2
  - Bottom-Left (BL): Tag 0
  - Bottom-Right (BR): Tag 1

Fits all 4 markers on 1 single A4 sheet, aligned for half-cut / 2x2 sticker paper.
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

# Generate 1000x1000px high-contrast square markers with 10% white quiet zone
for tid, label, filename in tag_info:
    if hasattr(cv2.aruco, 'generateImageMarker'):
        raw_marker = cv2.aruco.generateImageMarker(dictionary, tid, 800)
    else:
        raw_marker = cv2.aruco.drawMarker(dictionary, tid, 800)

    # 1000x1000 white canvas with 100px white quiet zone border
    canvas = np.ones((1000, 1000), dtype=np.uint8) * 255
    canvas[100:900, 100:900] = raw_marker

    out_path = os.path.join(MARKERS_DIR, filename)
    cv2.imwrite(out_path, canvas)
    print(f"  [OK] Created clean square marker: {filename}")

# Generate A4 Single-Sheet 2x2 Layout (print_markers.html)
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>A4 Sticker Sheet - 4 Whiteboard Markers (2x2 Grid)</title>
<style>
  @page {
    size: A4 portrait;
    margin: 6mm;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    margin: 0;
    padding: 0;
    background: #fff;
    color: #000;
  }
  .instructions {
    text-align: center;
    padding: 12px;
    background: #f0f4f8;
    border-bottom: 2px solid #ccc;
    margin-bottom: 8px;
  }
  .instructions h2 {
    margin: 0 0 6px 0;
    font-size: 18px;
  }
  .instructions p {
    margin: 0 0 10px 0;
    font-size: 13px;
    color: #444;
  }
  .print-btn {
    font-size: 16px;
    padding: 8px 22px;
    cursor: pointer;
    background: #007aff;
    color: #fff;
    border: none;
    border-radius: 6px;
    font-weight: bold;
  }

  /* A4 2x2 Grid Container */
  .a4-page {
    width: 198mm;
    height: 282mm;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-template-rows: 1fr 1fr;
    border: 1px dashed #bbb;
    position: relative;
  }

  /* Halfway Cut-Line Indicators (Horizontal & Vertical Center) */
  .cut-line-h {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 0;
    border-top: 1px dashed #888;
    pointer-events: none;
  }
  .cut-line-v {
    position: absolute;
    left: 50%;
    top: 0;
    bottom: 0;
    width: 0;
    border-left: 1px dashed #888;
    pointer-events: none;
  }

  .sticker-quad {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 6mm;
    text-align: center;
  }

  .marker-img {
    width: 88mm;
    height: 88mm;
    max-width: 3.5in;
    max-height: 3.5in;
    display: block;
    border: 1px solid #ddd;
  }

  .marker-title {
    font-size: 15px;
    font-weight: 800;
    margin-top: 6px;
    letter-spacing: 0.5px;
  }

  .marker-desc {
    font-size: 11px;
    color: #555;
    margin-top: 2px;
    font-weight: 600;
  }

  @media print {
    .no-print { display: none !important; }
    body { margin: 0; padding: 0; }
    .a4-page {
      border: none;
      width: 100%;
      height: 100vh;
      page-break-inside: avoid;
    }
  }
</style>
</head>
<body>

<div class="instructions no-print">
  <h2>🎯 A4 Sticker Sheet — All 4 Markers on 1 Page (2x2 Grid)</h2>
  <p>Formatted for A4 sticker paper with a halfway split. 2 markers per column, exactly ~3.5" to 4" each.</p>
  <button class="print-btn" onclick="window.print()">
    🖨️ Print 1-Page Sticker Sheet (Ctrl + P)
  </button>
</div>

<div class="a4-page">
  <!-- Halfway Cut Guidlines -->
  <div class="cut-line-h"></div>
  <div class="cut-line-v"></div>

  <!-- TOP-LEFT: TAG 3 -->
  <div class="sticker-quad">
    <img class="marker-img" src="markers/tag3_top_left.png" alt="Tag 3">
    <div class="marker-title">TAG 3 ➔ TOP-LEFT (TL)</div>
    <div class="marker-desc">Stick on Upper-Left Corner of Whiteboard</div>
  </div>

  <!-- TOP-RIGHT: TAG 2 -->
  <div class="sticker-quad">
    <img class="marker-img" src="markers/tag2_top_right.png" alt="Tag 2">
    <div class="marker-title">TAG 2 ➔ TOP-RIGHT (TR)</div>
    <div class="marker-desc">Stick on Upper-Right Corner of Whiteboard</div>
  </div>

  <!-- BOTTOM-LEFT: TAG 0 -->
  <div class="sticker-quad">
    <img class="marker-img" src="markers/tag0_bottom_left.png" alt="Tag 0">
    <div class="marker-title">TAG 0 ➔ BOTTOM-LEFT (BL)</div>
    <div class="marker-desc">Stick on Lower-Left Corner of Whiteboard</div>
  </div>

  <!-- BOTTOM-RIGHT: TAG 1 -->
  <div class="sticker-quad">
    <img class="marker-img" src="markers/tag1_bottom_right.png" alt="Tag 1">
    <div class="marker-title">TAG 1 ➔ BOTTOM-RIGHT (BR)</div>
    <div class="marker-desc">Stick on Lower-Right Corner of Whiteboard</div>
  </div>
</div>

</body>
</html>
"""

html_path = os.path.join(OUTPUT_DIR, "print_markers.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n[OK] Generated clean square markers in: {MARKERS_DIR}")
print(f"[OK] Saved 1-page A4 sticker layout: {html_path}")
print("   (Open print_markers.html in browser and print 1 page!)")
