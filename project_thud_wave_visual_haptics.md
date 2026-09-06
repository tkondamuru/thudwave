# Project THUD-WAVE 🌊⚡
### The Kinetic Whiteboard Resonance Engine (a.k.a. *"Boing-O-Vision"*)

> *"When a ball hits a wall, the wall should scream in neon."*

---

## 1. Executive Summary: What is "Project THUD-WAVE"?

**Project THUD-WAVE** is an interactive pseudo-haptic system that turns a standard, boring office whiteboard into an arcade-style, responsive surface. 

When a physical ball strikes the rigid whiteboard:
1. The **Front Camera** catches the exact physical impact coordinate $(X, Y)$ within **$33\text{ ms}$**.
2. The **Projector** instantly blasts an expanding **kinetic shockwave ("visual vibration")** right beneath the ball.
3. A paired **Bluetooth Speaker** booms a deep sub-bass *"THUD!"* or arcade *"BULLSEYE!"*.

To the human brain, seeing a visual shockwave ripple outward from the exact physical point of impact creates an incredible sensory illusion: **the physical whiteboard appears to ripple like water or vibrate like a drum membrane!**

---

## 2. The Visual "Vibration" FX Suite

The projector renders on a **pure black background** (which emits zero light, keeping the physical whiteboard looking completely normal). The instant contact occurs, it unleashes one of four visual vibration styles:

```
          Physical Ball Impact
                 (X, Y)
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   [ Audio FX ]        [ Visual Vibration FX ]
   "BOOM! / BOING!"    Expanding Neon Shockwave
```

### Vibration Style A: The Sci-Fi Sonic Ripple (Default)
* **Visual:** Concentric neon cyan and electric blue shockwave rings expand outward from the impact point at $300\text{ px/second}$.
* **Decay:** Rings fade from 100% opacity to 0% over $300\text{ ms}$ ($9\text{ frames}$).
* **Sensation:** Looks like you threw a stone into a neon puddle.

### Vibration Style B: The "Cartoon BOING!" (Arcade Mode)
* **Visual:** A retro comic-book starburst explodes under the ball, flashing bright yellow and hot orange with little action lines radiating outward.
* **Text Overlay:** Floating retro pop-up: *"BAM!"*, *"POW!"*, or *"+100 PTS!"*.

### Vibration Style C: The Neon Splat-O-Matic
* **Visual:** An ink/paint splatter explodes outwards with randomized dripping droplet particles that run down the board and fade away.
* **Color:** Matches the player's team color (e.g. Electric Lime Green vs. Hot Magenta).

### Vibration Style D: The Matrix Grid Warp
* **Visual:** The whiteboard surface briefly reveals a digital glowing wireframe grid that physically bends, warps, and oscillates like a rubber sheet under the impact before snapping back flat.

---

## 3. "The Lazy Laptop Setup" (Angled Camera Perspective Freedom)

A major design goal is **zero physical hassle**: you shouldn't have to mount your laptop on a precarious 6-foot ladder centered in front of the board.

```
       [ Angled Laptop on Desk ]
             \
              \ (35° Side Angle)
               \
                ▼
        ┌──────────────────┐
        │ 3    ArUco     2 │
        │                  │
        │    WHITEBOARD    │
        │                  │
        │ 0              1 │
        └──────────────────┘
                ▲
                │ (Straight On)
        [ HY300 PRO Projector ]
```

### Why the Laptop Camera Angle Does NOT Matter:
* The whiteboard has **4 ArUco markers** at its corners (`#0 BL, #1 BR, #2 TR, #3 TL`).
* Even if your laptop sits on a side desk at a steep $35^\circ$ angle (making the whiteboard appear as a skewed trapezoid), OpenCV's **Planar Perspective Homography** mathematically "un-skews" the view:
  $$\mathbf{P}_{\text{flat}} = \mathbf{H}_{\text{perspective}} \cdot \mathbf{P}_{\text{angled\_camera}}$$
* The software treats the board as a flat $1920 \times 1080$ coordinate canvas. **You can put your laptop wherever your desk is!**

---

## 4. The 10-Second Projector Alignment Screen ("The Invisible Square")

To align the **Magcubic HY300 PRO** projector with your whiteboard:

### Step 1: Calibration Mode Launch
When you start the script, the projector displays the **Alignment Test Pattern**:
1. **Background:** 100% Black (invisible on the whiteboard).
2. **Perimeter:** A thin, pulsing neon green rectangular boundary border matching the physical whiteboard's 16:9 or 4:3 ratio.
3. **Center:** A bright red bullseye / crosshair directly in the center.

### Step 2: 10-Second Physical Placement
1. Point the projector at the whiteboard.
2. Use the projector's 180° rotatable base and the built-in 4-corner digital keystone on the remote until the neon border aligns with the physical whiteboard frame.
3. Check that the red bullseye lands in the physical center of the whiteboard.

### Step 3: Game On!
* Press **SPACEBAR**.
* The alignment lines vanish into pure black.
* The system is fully calibrated: every physical throw now triggers visual vibrations at the exact sub-centimeter impact location!

---

## 5. Technical Specifications Summary

| Feature | Specification |
| :--- | :--- |
| **Project Codename** | **THUD-WAVE** (The Whiteboard Resonance Engine) |
| **Detection Mode** | Single-Camera Physical Rebound Vertex ($\Delta X < 0$) |
| **Detection Latency** | $< 33\text{ ms}$ (within 1 frame of contact) |
| **Vibration FX Duration** | $250\text{ to }350\text{ ms}$ (smooth decay) |
| **Projector Resolution** | $1920 \times 1080$ Full HD |
| **Camera Perspective** | Any angle from $0^\circ$ to $45^\circ$ off-center |
| **Required Hardware** | Laptop Webcam + Magcubic HY300 PRO Projector |
| **Zero-Installation Support**| Runs natively in local Python/OpenCV environment |
